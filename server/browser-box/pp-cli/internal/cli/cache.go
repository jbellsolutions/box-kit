// Copyright 2026 jbellsolutions and contributors. Licensed under Apache-2.0. See LICENSE.
// pp:data-source local

package cli

import (
	"fmt"
	"net/url"
	"strings"
	"time"

	"github.com/spf13/cobra"

	"browser-box-pp-cli/internal/cliutil"
	"browser-box-pp-cli/internal/ledger"
	"browser-box-pp-cli/internal/store"
)

type cacheView struct {
	Found      bool           `json:"found"`
	URL        string         `json:"url"`
	Page       *store.PageRow `json:"page,omitempty"`
	AgeSeconds int64          `json:"age_seconds,omitempty"`
	Note       string         `json:"note,omitempty"`
}

func newNovelCacheCmd(flags *rootFlags) *cobra.Command {
	var list bool
	var maxAge, dbPath string
	var limit int

	cmd := &cobra.Command{
		Use:   "cache [url]",
		Short: "Get a page you already read back instantly, without opening a browser.",
		Long: strings.Trim(`
Every successful fetch or read made through this CLI is kept locally by URL.
cache re-emits the newest copy (title, final URL, text, links) with no call to
the box, so it opens no browser and costs nothing.

Use this command to re-emit a previously cached read/fetch result without
opening a browser again. Do NOT use this command when the page may have
changed and a fresh render is required; use 'read' instead.

A URL that was never read returns found=false with exit 0. --max-age treats
an older copy as missing.`, "\n"),
		Example: strings.Trim(`
  browser-box-pp-cli cache https://news.ycombinator.com --agent
  browser-box-pp-cli cache https://example.com --max-age 1h --agent --select found,page.title
  browser-box-pp-cli cache --list`, "\n"),
		Annotations: map[string]string{"mcp:read-only": "true", "pp:data-source": "local", "pp:happy-args": "url=https://example.com"},
		RunE: func(cmd *cobra.Command, args []string) error {
			if len(args) == 0 && cmd.Flags().NFlag() == 0 {
				return cmd.Help()
			}
			if dryRunOK(flags) {
				return writeDryRun(cmd.OutOrStdout(), flags, "cache")
			}
			if !list && len(args) == 0 {
				_ = cmd.Usage()
				return usageErr(fmt.Errorf("give a URL to look up, or --list"))
			}
			if len(args) > 0 {
				if u, err := url.Parse(args[0]); err != nil || (u.Scheme != "http" && u.Scheme != "https") || u.Host == "" {
					return usageErr(fmt.Errorf("%q is not an http(s) URL", args[0]))
				}
			}
			var ageLimit time.Duration
			if maxAge != "" {
				d, err := cliutil.ParseDurationLoose(maxAge)
				if err != nil || d <= 0 {
					return usageErr(fmt.Errorf("--max-age %q: use a duration like 30m, 24h or 7d", maxAge))
				}
				ageLimit = d
			}
			db, found, err := openLedger(cmd.Context(), dbPath)
			if err != nil {
				return err
			}
			if found {
				defer db.Close()
			}

			if list {
				pages := make([]store.PageRow, 0)
				if found {
					if pages, err = db.Pages(cmd.Context(), limit); err != nil {
						return fmt.Errorf("listing cached pages: %w", err)
					}
				}
				if !wantsHumanTable(cmd.OutOrStdout(), flags) {
					return printJSONFiltered(cmd.OutOrStdout(), pages, flags)
				}
				if len(pages) == 0 {
					fmt.Fprintln(cmd.OutOrStdout(), "No cached pages yet. read or fetch a URL through this CLI first.")
					return nil
				}
				rows := make([][]string, 0, len(pages))
				for _, p := range pages {
					rows = append(rows, []string{p.FetchedAt[:19], p.Via, clipText(p.Title, 40), p.URL})
				}
				return flags.printTable(cmd, []string{"FETCHED (UTC)", "VIA", "TITLE", "URL"}, rows)
			}

			url := args[0]
			view := cacheView{URL: url}
			if found {
				page, err := db.LatestPage(cmd.Context(), url)
				if err != nil {
					return fmt.Errorf("reading the page cache: %w", err)
				}
				if page != nil {
					fetched, _ := time.Parse(ledger.TimeFormat, page.FetchedAt)
					age := time.Since(fetched)
					if ageLimit > 0 && age > ageLimit {
						view.Note = fmt.Sprintf("the cached copy is %s old, older than --max-age %s; run read for a fresh one", age.Round(time.Second), maxAge)
					} else {
						view.Found, view.Page, view.AgeSeconds = true, page, int64(age.Seconds())
					}
				}
			}
			if !view.Found && view.Note == "" {
				view.Note = "not cached: run 'browser-box-pp-cli read --url " + url + "' first"
			}
			if !wantsHumanTable(cmd.OutOrStdout(), flags) {
				return printJSONFiltered(cmd.OutOrStdout(), view, flags)
			}
			if !view.Found {
				fmt.Fprintln(cmd.OutOrStdout(), view.Note)
				return nil
			}
			p := view.Page
			fmt.Fprintf(cmd.OutOrStdout(), "%s\n%s\n(cached %s ago via %s)\n\n%s\n", p.Title, p.FinalURL,
				(time.Duration(view.AgeSeconds) * time.Second).String(), p.Via, p.Text)
			return nil
		},
	}
	cmd.Flags().BoolVar(&list, "list", false, "List cached URLs, newest first, instead of printing one page")
	cmd.Flags().StringVar(&maxAge, "max-age", "", "Treat a copy older than this as missing (30m, 24h, 7d)")
	cmd.Flags().IntVar(&limit, "limit", 50, "Maximum pages for --list")
	cmd.Flags().StringVar(&dbPath, "db", "", "Local ledger database path (default: the CLI's data directory)")
	return cmd
}
