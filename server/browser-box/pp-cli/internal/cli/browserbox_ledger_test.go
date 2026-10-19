// Copyright 2026 jbellsolutions and contributors. Licensed under Apache-2.0. See LICENSE.

package cli

import (
	"bytes"
	"encoding/base64"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync/atomic"
	"testing"

	"browser-box-pp-cli/internal/cliutil/testenv"
)

// fakeBox answers like browser-box's HTTP door.
type fakeBox struct {
	laneBusyFor atomic.Int32 // this many reads answer lane busy first
	steelUp     atomic.Bool
	reads       atomic.Int32
}

func (b *fakeBox) handler(t *testing.T) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("Authorization") != "Bearer test-token" {
			w.WriteHeader(401)
			io.WriteString(w, `{"error":"unauthorized"}`)
			return
		}
		body, _ := io.ReadAll(r.Body)
		var args map[string]any
		_ = json.Unmarshal(body, &args)
		w.Header().Set("Content-Type", "application/json")
		switch r.URL.Path {
		case "/api/v1/read":
			b.reads.Add(1)
			if b.laneBusyFor.Load() > 0 {
				b.laneBusyFor.Add(-1)
				w.WriteHeader(422)
				io.WriteString(w, `{"error":"another job has held the browser lane for longer than 120s (task pid=9)","tool":"read"}`)
				return
			}
			url, _ := args["url"].(string)
			if strings.Contains(url, "127.0.0.1") {
				w.WriteHeader(422)
				io.WriteString(w, `{"error":"refused: loopback address","tool":"read"}`)
				return
			}
			out := map[string]any{"title": "Title of " + url, "final_url": url + "/", "text": "Pricing for " + url + " starts at ten dollars", "links": []string{"https://iana.org"}}
			if shot, _ := args["screenshot"].(bool); shot {
				out["screenshot_base64"] = base64.StdEncoding.EncodeToString([]byte("\xff\xd8JPEGDATA"))
			}
			json.NewEncoder(w).Encode(out)
		case "/api/v1/status":
			up := b.steelUp.Load()
			working := []string{"fetch", "status"}
			if up {
				working = append(working, "read")
			}
			json.NewEncoder(w).Encode(map[string]any{
				"components":        []any{map[string]any{"name": "steel (the browser)", "up": up}},
				"browser_lane":      "free",
				"tools_working_now": working,
				"tools_unavailable": []any{},
			})
		case "/api/v1/session":
			io.WriteString(w, `{"session_id":"sess_abc","status":"live"}`)
		default:
			w.WriteHeader(404)
			io.WriteString(w, `{"error":"no tool"}`)
		}
	})
}

func runCLI(t *testing.T, args ...string) (string, error) {
	t.Helper()
	cmd := RootCmd()
	cmd.SetArgs(args)
	var out, errOut bytes.Buffer
	cmd.SetOut(&out)
	cmd.SetErr(&errOut)
	err := cmd.Execute()
	return out.String(), err
}

func setupBox(t *testing.T) *fakeBox {
	t.Helper()
	testenv.Isolate(t)
	box := &fakeBox{}
	box.steelUp.Store(true)
	srv := httptest.NewServer(box.handler(t))
	t.Cleanup(srv.Close)
	t.Setenv("BROWSER_BOX_BASE_URL", srv.URL)
	t.Setenv("BROWSER_BOX_TOKEN", "test-token")
	t.Setenv("BROWSER_BOX_NO_LEDGER", "")
	return box
}

func decode[T any](t *testing.T, out string) T {
	t.Helper()
	var v T
	if err := json.Unmarshal([]byte(out), &v); err != nil {
		t.Fatalf("output is not the expected JSON: %v\n%s", err, out)
	}
	return v
}

func TestLedgerRecordsReadsAndServesCacheFindHistory(t *testing.T) {
	setupBox(t)
	if _, err := runCLI(t, "read", "--url", "https://example.com", "--json"); err != nil {
		t.Fatalf("read: %v", err)
	}
	if _, err := runCLI(t, "read", "--url", "http://127.0.0.1", "--json"); err == nil {
		t.Fatal("a refused read must exit non-zero")
	}

	out, err := runCLI(t, "cache", "https://example.com", "--json")
	if err != nil {
		t.Fatalf("cache: %v", err)
	}
	hit := decode[cacheView](t, out)
	if !hit.Found || hit.Page == nil || hit.Page.Title != "Title of https://example.com" || !strings.Contains(hit.Page.Text, "Pricing") {
		t.Fatalf("cache hit = %+v", hit)
	}
	out, _ = runCLI(t, "cache", "https://never-read.example", "--json")
	if miss := decode[cacheView](t, out); miss.Found || miss.Note == "" {
		t.Fatalf("cache miss = %+v", miss)
	}

	out, _ = runCLI(t, "find", "pricing", "--json")
	hits := decode[[]map[string]any](t, out)
	if len(hits) != 1 || hits[0]["url"] != "https://example.com" {
		t.Fatalf("find pricing = %s", out)
	}
	out, _ = runCLI(t, "find", "kubernetes", "--json")
	if none := decode[[]map[string]any](t, out); len(none) != 0 {
		t.Fatalf("negative find matched: %s", out)
	}

	out, _ = runCLI(t, "history", "--json")
	rows := decode[[]map[string]any](t, out)
	if len(rows) != 2 {
		t.Fatalf("history rows = %d: %s", len(rows), out)
	}
	if rows[0]["status"] != "refused" || rows[1]["status"] != "ok" {
		t.Fatalf("history newest-first statuses = %v, %v", rows[0]["status"], rows[1]["status"])
	}
	out, _ = runCLI(t, "history", "--status", "failed", "--json")
	if failed := decode[[]map[string]any](t, out); len(failed) != 1 {
		t.Fatalf("history --status failed = %s", out)
	}
	if _, err := runCLI(t, "history", "--since", "banana"); err == nil {
		t.Fatal("a bad --since must be a usage error")
	}
}

func TestDriftReportsOnlyRealChanges(t *testing.T) {
	box := setupBox(t)
	out, err := runCLI(t, "drift", "--json")
	if err != nil {
		t.Fatalf("drift: %v", err)
	}
	first := decode[driftView](t, out)
	if first.Note == "" || len(first.Changes) != 0 {
		t.Fatalf("first drift should set a baseline: %+v", first)
	}
	out, _ = runCLI(t, "drift", "--json")
	if same := decode[driftView](t, out); len(same.Changes) != 0 {
		t.Fatalf("no change should be no drift: %s", out)
	}
	box.steelUp.Store(false)
	out, _ = runCLI(t, "drift", "--json")
	changed := decode[driftView](t, out)
	whats := map[string]bool{}
	for _, c := range changed.Changes {
		whats[c.What] = true
	}
	if !whats["component steel (the browser)"] || !whats["tool read"] || len(changed.Changes) != 2 {
		t.Fatalf("drift after steel went down = %+v", changed.Changes)
	}
}

func TestQueueRetriesABusyLane(t *testing.T) {
	box := setupBox(t)
	box.laneBusyFor.Store(1)
	out, err := runCLI(t, "queue", "read", "https://a.example", "http://127.0.0.1", "--backoff", "1ms", "--json")
	if err != nil {
		t.Fatalf("queue read: %v", err)
	}
	view := decode[queueView](t, out)
	if view.Read != 1 || view.Failed != 1 || len(view.Results) != 2 {
		t.Fatalf("queue view = %+v", view)
	}
	if !view.Results[0].OK || view.Results[0].Attempts != 2 {
		t.Fatalf("the busy lane should have been retried once: %+v", view.Results[0])
	}
	if view.Results[1].OK || !strings.Contains(view.Results[1].Error, "loopback") || view.Results[1].Attempts != 1 {
		t.Fatalf("a refusal must not be retried: %+v", view.Results[1])
	}
	if view.Results[0].Text != "" {
		t.Fatal("text is only included with --text")
	}
	box.laneBusyFor.Store(5)
	if _, err := runCLI(t, "queue", "read", "https://b.example", "--retries", "1", "--backoff", "1ms", "--json"); err == nil {
		t.Fatal("a batch where nothing was read must exit non-zero")
	}
}

func TestAliasNamesTheLastCreatedSession(t *testing.T) {
	setupBox(t)
	if _, err := runCLI(t, "alias", "set", "crm"); err == nil {
		t.Fatal("alias set with no session created yet must fail")
	}
	if _, err := runCLI(t, "session", "--action", "create", "--json"); err != nil {
		t.Fatalf("session create: %v", err)
	}
	if _, err := runCLI(t, "alias", "set", "crm", "--note", "HubSpot"); err != nil {
		t.Fatalf("alias set: %v", err)
	}
	out, err := runCLI(t, "alias", "get", "crm", "--json")
	if err != nil {
		t.Fatalf("alias get: %v", err)
	}
	if a := decode[map[string]any](t, out); a["session_id"] != "sess_abc" || a["note"] != "HubSpot" {
		t.Fatalf("alias = %s", out)
	}
	if _, err := runCLI(t, "alias", "get", "nope"); err == nil {
		t.Fatal("a missing alias must exit non-zero")
	}
	out, _ = runCLI(t, "alias", "--json")
	if list := decode[[]map[string]any](t, out); len(list) != 1 {
		t.Fatalf("alias list = %s", out)
	}
}

func TestReadOutWritesTheScreenshot(t *testing.T) {
	setupBox(t)
	dir := t.TempDir()
	path := filepath.Join(dir, "shot.jpg")
	out, err := runCLI(t, "read", "--url", "https://example.com", "--screenshot", "--out", path, "--json")
	if err != nil {
		t.Fatalf("read --out: %v", err)
	}
	if strings.Contains(out, "screenshot_base64") || !strings.Contains(out, "screenshot_file") {
		t.Fatalf("stdout should carry the file path, not the base64: %s", out)
	}
	got, err := os.ReadFile(path)
	if err != nil || string(got) != "\xff\xd8JPEGDATA" {
		t.Fatalf("screenshot file = %q, %v", got, err)
	}
}

func TestTruncatedBodyIsAnErrorNotASuccess(t *testing.T) {
	testenv.Isolate(t)
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Length", "500")
		w.WriteHeader(200)
		io.WriteString(w, `{"title":"x","text":"abc`)
	}))
	t.Cleanup(srv.Close)
	t.Setenv("BROWSER_BOX_BASE_URL", srv.URL)
	t.Setenv("BROWSER_BOX_TOKEN", "test-token")
	out, err := runCLI(t, "queue", "read", "https://a.example", "--retries", "0", "--json")
	if err == nil {
		t.Fatalf("a truncated body must not read as success: %s", out)
	}
	hist, _ := runCLI(t, "history", "--json")
	rows := decode[[]map[string]any](t, hist)
	if len(rows) == 0 || rows[0]["ok"] != false || !strings.Contains(rows[0]["error"].(string), "reading the response") {
		t.Fatalf("the ledger must record the broken read as an error: %s", hist)
	}
}

func TestBrowserCallsAreTaggedWithTheOpenSession(t *testing.T) {
	setupBox(t)
	runCLI(t, "session", "--action", "create", "--json")
	runCLI(t, "read", "--url", "https://example.com", "--json")
	runCLI(t, "session", "--action", "release", "--session-id", "sess_abc", "--json")
	runCLI(t, "read", "--url", "https://example.org", "--json")
	runCLI(t, "alias", "set", "crm", "sess_abc")
	out, _ := runCLI(t, "history", "--session", "crm", "--json")
	rows := decode[[]map[string]any](t, out)
	var urls []string
	for _, r := range rows {
		if r["tool"] == "read" {
			urls = append(urls, r["summary"].(string))
		}
	}
	if len(urls) != 1 || urls[0] != "https://example.com" {
		t.Fatalf("only the read made while sess_abc was open belongs to it: %v (%s)", urls, out)
	}
}

func TestOutWithoutScreenshotSaysSo(t *testing.T) {
	setupBox(t)
	path := filepath.Join(t.TempDir(), "none.jpg")
	out, _ := runCLI(t, "read", "--url", "https://example.com", "--out", path, "--json")
	if !strings.Contains(out, "screenshot_error") {
		t.Fatalf("--out without --screenshot must explain itself: %s", out)
	}
	if _, err := os.Stat(path); err == nil {
		t.Fatal("no file should be written")
	}
}

func TestAliasRmOnAFreshLedger(t *testing.T) {
	setupBox(t)
	out, err := runCLI(t, "alias", "rm", "nope", "--json")
	if err != nil || !strings.Contains(out, `"removed": false`) {
		t.Fatalf("alias rm = %s, %v", out, err)
	}
}

func TestDryRunSendsNothingAndSaysWhatItWouldDo(t *testing.T) {
	box := setupBox(t)
	for _, args := range [][]string{
		{"read", "--url", "https://example.com"},
		{"act", "--command", "open https://example.com"},
		{"doctor"},
		{"profile", "list"},
	} {
		out, err := runCLI(t, append(args, "--dry-run", "--json")...)
		if err != nil {
			t.Fatalf("%v: %v", args, err)
		}
		got := decode[dryRunResult](t, out)
		if !got.DryRun || got.Action == "" {
			t.Errorf("%v: %+v", args, got)
		}
	}
	if n := box.reads.Load(); n != 0 {
		t.Errorf("dry run reached the box %d times", n)
	}
}

func TestCacheRefusesANonURL(t *testing.T) {
	setupBox(t)
	if _, err := runCLI(t, "cache", "not-a-url"); err == nil {
		t.Fatal("cache accepted a non-URL")
	}
}
