// Copyright 2026 jbellsolutions and contributors. Licensed under Apache-2.0. See LICENSE.
// pp:data-source live

package cli

import (
	"bufio"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"strings"
	"time"

	"github.com/spf13/cobra"

	"browser-box-pp-cli/internal/client"
	"browser-box-pp-cli/internal/ledger"
)

type queuedRead struct {
	URL      string `json:"url"`
	OK       bool   `json:"ok"`
	Attempts int    `json:"attempts"`
	Title    string `json:"title,omitempty"`
	FinalURL string `json:"final_url,omitempty"`
	Chars    int    `json:"text_chars,omitempty"`
	Text     string `json:"text,omitempty"`
	Error    string `json:"error,omitempty"`
}

type queueView struct {
	Results []queuedRead `json:"results"`
	Read    int          `json:"read"`
	Failed  int          `json:"failed"`
	Note    string       `json:"note,omitempty"`
}

func newNovelQueueCmd(flags *rootFlags) *cobra.Command {
	cmd := &cobra.Command{
		Use:   "queue",
		Short: "Read a list of pages one after another, retrying when the box answers \"busy\".",
		Long: strings.Trim(`
Reads on the box run side by side, each in a hosted browser of its own, but a
call can still be refused as busy (a session or an Orgo computer in use by
another call). queue runs a batch one call at a time and, on a busy refusal,
backs off and retries instead of failing the batch.

Use this command for a list of pages you want read in order with one tidy
ledger. Do NOT use this command for a single read/act/task call; call that tool
directly instead.`, "\n"),
		Example: "  browser-box-pp-cli queue read https://example.com https://news.ycombinator.com --agent",
	}
	return cmd
}

func readWithRetry(cmd *cobra.Command, c *client.Client, url string, retries int, wait time.Duration) queuedRead {
	row := queuedRead{URL: url}
	for attempt := 0; attempt <= retries; attempt++ {
		row.Attempts = attempt + 1
		data, _, err := c.PostWithParams(cmd.Context(), "/api/v1/read", nil, map[string]any{"url": url})
		if err == nil {
			var page struct {
				Title    string `json:"title"`
				FinalURL string `json:"final_url"`
				Text     string `json:"text"`
				Error    string `json:"error"`
			}
			_ = json.Unmarshal(data, &page)
			if page.Error == "" {
				row.OK, row.Title, row.FinalURL, row.Chars, row.Text, row.Error = true, page.Title, page.FinalURL, len(page.Text), page.Text, ""
				return row
			}
			err = errors.New(page.Error)
		}
		row.Error = apiErrorText(err)
		if !ledger.IsLaneBusy(row.Error) || attempt == retries {
			return row
		}
		fmt.Fprintf(cmd.ErrOrStderr(), "busy; retrying %s in %s\n", url, wait)
		select {
		case <-cmd.Context().Done():
			row.Error = "cancelled while waiting to retry a busy refusal"
			return row
		case <-time.After(wait):
		}
		wait *= 2
	}
	return row
}

// apiErrorText prefers the box's own error message over the HTTP wrapper.
func apiErrorText(err error) string {
	var apiErr *client.APIError
	if errors.As(err, &apiErr) {
		var body struct {
			Error string `json:"error"`
		}
		if json.Unmarshal([]byte(apiErr.Body), &body) == nil && body.Error != "" {
			return body.Error
		}
		if strings.TrimSpace(apiErr.Body) != "" {
			return apiErr.Body
		}
	}
	return err.Error()
}

func readURLList(stdin io.Reader, path string) ([]string, error) {
	var r io.Reader = stdin
	if path != "-" {
		f, err := os.Open(path) // #nosec G304 -- the caller names the file to read with --file
		if err != nil {
			return nil, fmt.Errorf("--file: %w", err)
		}
		defer f.Close()
		r = f
	}
	out := make([]string, 0)
	scanner := bufio.NewScanner(r)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		out = append(out, line)
	}
	return out, scanner.Err()
}
