// Copyright 2026 jbellsolutions and contributors. Licensed under Apache-2.0. See LICENSE.

package cli

// The write-through ledger. browser-box keeps only its last 10 calls, so this
// CLI keeps its own record: every tool call made through it (and through its
// MCP server, which builds clients the same way) is written to the local
// store by a transport wrapped around the generated client. history, cache,
// find and drift read what this writes.

import (
	"bytes"
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"sync/atomic"
	"time"

	"github.com/spf13/cobra"

	"browser-box-pp-cli/internal/client"
	"browser-box-pp-cli/internal/cliutil"
	"browser-box-pp-cli/internal/ledger"
	"browser-box-pp-cli/internal/store"
)

const bbCLIName = "browser-box-pp-cli"

// screenshotOut points at the --out value of the newest command tree: the
// screenshot is written there and replaced in the output by its path. A
// pointer swapped atomically, because the MCP server rebuilds the tree while
// other calls are in flight.
var screenshotOut atomic.Pointer[string]

func screenshotPath() string {
	if p := screenshotOut.Load(); p != nil {
		return *p
	}
	return ""
}

// ledgerPath is one file for every process: the CLI, its MCP server and the
// CLI commands that server runs. It must not depend on per-command state such
// as the credential scope, or a server and a CLI would write different files.
func ledgerPath() string {
	dir, err := cliutil.DataDir()
	if err != nil {
		home, _ := os.UserHomeDir()
		dir = filepath.Join(home, ".local", "share", bbCLIName)
	}
	return filepath.Join(dir, "ledger.db")
}

func init() {
	registerClientHook(func(c *client.Client) error {
		if c == nil {
			return nil
		}
		// status and tools are the only GETs, and both report what is true
		// right now: a cached answer would be a wrong answer.
		c.NoCache = true
		if c.HTTPClient == nil || os.Getenv("BROWSER_BOX_NO_LEDGER") != "" {
			return nil
		}
		if _, wrapped := c.HTTPClient.Transport.(*ledgerTransport); wrapped {
			return nil
		}
		base := c.HTTPClient.Transport
		if base == nil {
			base = http.DefaultTransport
		}
		c.HTTPClient.Transport = &ledgerTransport{base: base}
		return nil
	})
	registerNovelCommand(func(root *cobra.Command, flags *rootFlags) {
		out := new(string)
		for _, name := range []string{"read", "computer"} {
			cmd, _, err := root.Find([]string{name})
			if err != nil || cmd == root || cmd.Name() != name || cmd.Flags().Lookup("out") != nil {
				continue
			}
			cmd.Flags().StringVar(out, "out", "",
				"Save the screenshot to this file (JPEG from read --screenshot, PNG from computer) and print its path instead of the base64")
		}
		screenshotOut.Store(out)
		// The generic sync/search/import/export and project-management views
		// assume listable resources, assignees and projects. The box has none:
		// its history lives in the ledger (history, cache, find). Keep them
		// callable, out of sight.
		for _, name := range []string{"load", "orphans", "stale", "sync", "search", "import", "export", "workflow"} {
			if cmd, _, err := root.Find([]string{name}); err == nil && cmd != root && cmd.Name() == name {
				cmd.Hidden = true
				if cmd.Annotations == nil {
					cmd.Annotations = map[string]string{}
				}
				cmd.Annotations["mcp:hidden"] = "true"
			}
		}
		honourDryRun(root, flags)
	})
}

// dryRunTools are the box tools a command sends as POST /api/v1/<tool>.
var dryRunTools = []string{"act", "computer", "fetch", "read", "session", "task"}

// dryRunLocal are commands whose --dry-run would otherwise do the work anyway
// (doctor probes the box) or print something that is not a dry-run report.
var dryRunLocal = [][]string{{"doctor"}, {"sync"}, {"workflow", "archive"}, {"feedback", "list"}, {"profile", "list"}}

// honourDryRun makes --dry-run end every command above with one report,
// {"dry_run": true, "action": ...}, the shape agents check for. A tool
// command still prints the request it would send on stderr.
func honourDryRun(root *cobra.Command, flags *rootFlags) {
	wrap := func(path []string, action string, preview bool) {
		cmd, _, err := root.Find(path)
		if err != nil || cmd == root || cmd.Name() != path[len(path)-1] || cmd.RunE == nil {
			return
		}
		run := cmd.RunE
		cmd.RunE = func(cmd *cobra.Command, args []string) error {
			if !dryRunOK(flags) {
				return run(cmd, args)
			}
			if preview {
				out := cmd.OutOrStdout()
				cmd.SetOut(io.Discard)
				err := run(cmd, args)
				cmd.SetOut(out)
				if err != nil {
					return err
				}
			}
			return writeDryRunReport(cmd.OutOrStdout(), flags, action)
		}
	}
	for _, tool := range dryRunTools {
		wrap([]string{tool}, "POST /api/v1/"+tool, true)
	}
	for _, path := range dryRunLocal {
		wrap(path, strings.Join(path, " "), false)
	}
}

// writeDryRunReport is writeDryRun, but JSON whenever stdout is not a
// terminal, like every other output of this CLI.
func writeDryRunReport(w io.Writer, flags *rootFlags, action string) error {
	if flags.asJSON || flags.agent || !isTerminal(w) {
		return json.NewEncoder(w).Encode(dryRunResult{DryRun: true, Action: action, Would: action + "; nothing sent, nothing changed"})
	}
	return writeDryRun(w, flags, action)
}

type ledgerTransport struct {
	base http.RoundTripper
}

func (t *ledgerTransport) RoundTrip(req *http.Request) (*http.Response, error) {
	tool, isTool := ledger.ToolFromPath(req.Method, req.URL.Path)
	if !isTool {
		return t.base.RoundTrip(req)
	}
	reqBody := requestBody(req)
	started := time.Now()
	resp, err := t.base.RoundTrip(req)
	took := time.Since(started)
	if err != nil {
		call, _ := ledger.Build(tool, reqBody, nil, 0, took, started)
		call.Error = err.Error()
		call.Status = "error"
		recordCall(req.Context(), call, nil, nil)
		return nil, err
	}
	if resp.Header.Get("Content-Encoding") != "" && !resp.Uncompressed {
		return resp, nil // an encoding we would have to decode ourselves: pass through unrecorded
	}
	body, readErr := io.ReadAll(resp.Body)
	_ = resp.Body.Close()
	if readErr != nil {
		// Hand the failure on: the caller must see a broken body as an error,
		// not as the truncated JSON read so far.
		resp.Body = io.NopCloser(io.MultiReader(bytes.NewReader(body), failingReader{readErr}))
		call, _ := ledger.Build(tool, reqBody, nil, resp.StatusCode, took, started)
		call.OK, call.Status, call.Error = false, "error", "reading the response: "+readErr.Error()
		recordCall(req.Context(), call, nil, nil)
		return resp, nil
	}
	if out := screenshotPath(); out != "" && resp.StatusCode >= 200 && resp.StatusCode < 300 && (tool == "read" || tool == "computer") {
		body = saveScreenshot(body, out)
	}
	resp.Body = io.NopCloser(bytes.NewReader(body))
	resp.ContentLength = int64(len(body))
	resp.Header.Del("Content-Length")

	stored := ledger.WithoutScreenshot(body)
	call, page := ledger.Build(tool, reqBody, stored, resp.StatusCode, took, started)
	var snapshot []byte
	if tool == "status" && call.OK {
		snapshot = stored
	}
	recordCall(req.Context(), call, page, snapshot)
	return resp, nil
}

type failingReader struct{ err error }

func (r failingReader) Read([]byte) (int, error) { return 0, r.err }

// requestBody reads the request's arguments through GetBody, leaving the
// request itself untouched. Without GetBody the arguments go unrecorded.
func requestBody(req *http.Request) []byte {
	if req.Body == nil || req.Body == http.NoBody || req.GetBody == nil {
		return nil
	}
	rc, err := req.GetBody()
	if err != nil {
		return nil
	}
	defer rc.Close()
	b, _ := io.ReadAll(rc)
	return b
}

// recordCall never fails the call it records: a ledger that cannot be
// written is reported on stderr and the command carries on. It outlives a
// cancelled command (the call did happen) but not by more than a few seconds.
func recordCall(ctx context.Context, call ledger.Call, page *ledger.Page, snapshot []byte) {
	ctx, cancel := context.WithTimeout(context.WithoutCancel(ctx), 5*time.Second)
	defer cancel()
	db, err := store.OpenWithContext(ctx, ledgerPath())
	if err == nil {
		err = db.RecordCall(ctx, call, page, snapshot)
		_ = db.Close()
	}
	if err != nil {
		fmt.Fprintf(os.Stderr, "warning: local call ledger not written (%s): %v\n", ledgerPath(), err)
	}
}

// saveScreenshot writes screenshot_base64 to path and replaces it in the
// body with screenshot_file and screenshot_bytes. On any failure the body is
// returned unchanged, with the reason in screenshot_error.
func saveScreenshot(body []byte, path string) []byte {
	var obj map[string]any
	if json.Unmarshal(body, &obj) != nil {
		return body
	}
	fail := func(err error) []byte {
		obj["screenshot_error"] = err.Error()
		out, _ := json.Marshal(obj)
		return out
	}
	encoded, _ := obj["screenshot_base64"].(string)
	if encoded == "" {
		if _, isError := obj["error"]; isError {
			return body
		}
		return fail(fmt.Errorf("--out was given but the answer has no screenshot: add --screenshot to read, or use computer --action screenshot"))
	}
	raw, err := base64.StdEncoding.DecodeString(encoded)
	if err != nil {
		return fail(fmt.Errorf("screenshot is not base64: %w", err))
	}
	abs, err := filepath.Abs(path)
	if err != nil {
		return fail(err)
	}
	if err := os.WriteFile(abs, raw, 0o600); err != nil {
		return fail(fmt.Errorf("writing %s: %w", abs, err))
	}
	delete(obj, "screenshot_base64")
	obj["screenshot_file"] = abs
	obj["screenshot_bytes"] = len(raw)
	out, err := json.Marshal(obj)
	if err != nil {
		return body
	}
	return out
}

// openLedger opens the ledger read-only for a reading command. A missing
// file, or one without ledger tables, is not an error: nothing has been
// recorded there yet.
func openLedger(ctx context.Context, dbPath string) (*store.Store, bool, error) {
	if dbPath == "" {
		dbPath = ledgerPath()
	}
	return store.OpenLedgerReader(ctx, dbPath)
}

// openLedgerForWrite opens (creating if needed) the ledger for a command
// that changes it.
func openLedgerForWrite(ctx context.Context, dbPath string) (*store.Store, error) {
	if dbPath == "" {
		dbPath = ledgerPath()
	}
	db, err := store.OpenWithContext(ctx, dbPath)
	if err != nil {
		return nil, fmt.Errorf("opening local ledger %s: %w", dbPath, err)
	}
	return db, nil
}
