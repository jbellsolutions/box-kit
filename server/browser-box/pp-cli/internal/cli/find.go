// Copyright 2026 jbellsolutions and contributors. Licensed under Apache-2.0. See LICENSE.
// pp:data-source local

package cli

import (
	"fmt"
	"strings"

	"github.com/spf13/cobra"

	"browser-box-pp-cli/internal/store"
)

func newNovelFindCmd(flags *rootFlags) *cobra.Command {
	var dbPath string
	var limit int

	cmd := &cobra.Command{
		Use:   "find [query]",
		Short: "Ask which page you read said something, across everything read so far.",
		Long: strings.Trim(`
Full-text search over every page body this CLI has cached from fetch and read.
All words must appear; results are ranked, one per URL, with a snippet around
the match. No call to the box is made.

Use this command for a full-text query across previously cached page bodies.
Do NOT use this command to filter ledger rows by tool or status; use 'history'
instead.`, "\n"),
		Example: strings.Trim(`
  browser-box-pp-cli find "pricing" --agent --select url,title
  browser-box-pp-cli find "free trial" --limit 5`, "\n"),
		Annotations: map[string]string{"mcp:read-only": "true", "pp:data-source": "local", "pp:happy-args": "query=pricing"},
		RunE: func(cmd *cobra.Command, args []string) error {
			if len(args) == 0 && cmd.Flags().NFlag() == 0 {
				return cmd.Help()
			}
			if dryRunOK(flags) {
				return writeDryRun(cmd.OutOrStdout(), flags, "find")
			}
			query := strings.TrimSpace(strings.Join(args, " "))
			if query == "" {
				_ = cmd.Usage()
				return usageErr(fmt.Errorf("give the words to search for"))
			}
			hits := make([]store.PageRow, 0)
			db, found, err := openLedger(cmd.Context(), dbPath)
			if err != nil {
				return err
			}
			if found {
				defer db.Close()
				if hits, err = db.SearchPages(cmd.Context(), query, limit); err != nil {
					return err
				}
			}
			if !wantsHumanTable(cmd.OutOrStdout(), flags) {
				return printJSONFiltered(cmd.OutOrStdout(), hits, flags)
			}
			if len(hits) == 0 {
				fmt.Fprintf(cmd.OutOrStdout(), "No cached page mentions %q. Only pages read or fetched through this CLI are searched.\n", query)
				return nil
			}
			for _, h := range hits {
				fmt.Fprintf(cmd.OutOrStdout(), "%s\n  %s  (%s, %s)\n  %s\n\n", firstNonBlank(h.Title, h.URL), h.URL, h.Via, h.FetchedAt[:10], h.Snippet)
			}
			return nil
		},
	}
	cmd.Flags().IntVar(&limit, "limit", 10, "Maximum pages to return")
	cmd.Flags().StringVar(&dbPath, "db", "", "Local ledger database path (default: the CLI's data directory)")
	return cmd
}

func firstNonBlank(values ...string) string {
	for _, v := range values {
		if strings.TrimSpace(v) != "" {
			return v
		}
	}
	return ""
}
