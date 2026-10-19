// Copyright 2026 jbellsolutions and contributors. Licensed under Apache-2.0. See LICENSE.
// pp:data-source local

package cli

import (
	"fmt"
	"strings"
	"time"

	"github.com/spf13/cobra"

	"browser-box-pp-cli/internal/cliutil"
	"browser-box-pp-cli/internal/store"
)

func newNovelHistoryCmd(flags *rootFlags) *cobra.Command {
	var tool, status, since, session, dbPath string
	var limit int

	cmd := &cobra.Command{
		Use:   "history",
		Short: "See every call you made through the box, what it cost and why it failed, long after the box forgot it.",
		Long: strings.Trim(`
The local call ledger: one row per call this CLI (or its MCP server) made to
the box, successful or not, with the tool, a one-line summary, status, HTTP
code, duration, error and task cost. The box itself keeps only its last 10.

Use this command to inspect or filter the raw local call ledger. Do NOT use
this command for a full-text query over page content; use 'find' instead.

--status takes ok, failed, or an exact status: done, refused, lane_busy,
needs_clarification, needs_confirmation, error.`, "\n"),
		Example: strings.Trim(`
  browser-box-pp-cli history --tool task --since 7d --agent
  browser-box-pp-cli history --status failed --limit 20
  browser-box-pp-cli history --agent --select tool,summary,status,cost_usd`, "\n"),
		Annotations: map[string]string{"mcp:read-only": "true", "pp:data-source": "local"},
		RunE: func(cmd *cobra.Command, args []string) error {
			if dryRunOK(flags) {
				return writeDryRun(cmd.OutOrStdout(), flags, "history")
			}
			filter := store.CallFilter{Tool: tool, Status: status, SessionID: session, Limit: limit}
			if since != "" {
				d, err := cliutil.ParseDurationLoose(since)
				if err != nil || d <= 0 {
					return usageErr(fmt.Errorf("--since %q: use a duration like 30m, 24h, 7d or 2w", since))
				}
				filter.Since = time.Now().Add(-d)
			}
			rows := make([]store.CallRow, 0)
			db, found, err := openLedger(cmd.Context(), dbPath)
			if err != nil {
				return err
			}
			if found {
				defer db.Close()
				if filter.SessionID != "" {
					if a, err := db.GetAlias(cmd.Context(), filter.SessionID); err == nil && a != nil {
						filter.SessionID = a.SessionID
					}
				}
				if rows, err = db.Calls(cmd.Context(), filter); err != nil {
					return fmt.Errorf("reading the call ledger: %w", err)
				}
			}
			if !wantsHumanTable(cmd.OutOrStdout(), flags) {
				return printJSONFiltered(cmd.OutOrStdout(), rows, flags)
			}
			if len(rows) == 0 {
				fmt.Fprintln(cmd.OutOrStdout(), "No calls recorded yet. Every call made through this CLI lands here.")
				return nil
			}
			table := make([][]string, 0, len(rows))
			var spent float64
			for _, r := range rows {
				cost := ""
				if r.CostUSD != nil {
					cost = fmt.Sprintf("$%.4f", *r.CostUSD)
					spent += *r.CostUSD
				}
				table = append(table, []string{r.At[:19], r.Tool, r.Status, fmt.Sprintf("%.1fs", float64(r.DurationMS)/1000), cost, clipText(r.Summary, 60)})
			}
			if err := flags.printTable(cmd, []string{"AT (UTC)", "TOOL", "STATUS", "TOOK", "COST", "SUMMARY"}, table); err != nil {
				return err
			}
			if spent > 0 {
				fmt.Fprintf(cmd.OutOrStdout(), "\nmodel spend in these rows: $%.4f\n", spent)
			}
			return nil
		},
	}
	cmd.Flags().StringVar(&tool, "tool", "", "Only calls to this tool: fetch, read, session, act, computer, task, status, tools")
	cmd.Flags().StringVar(&status, "status", "", "Only calls with this outcome: ok, failed, or an exact status such as lane_busy")
	cmd.Flags().StringVar(&since, "since", "", "Only calls newer than this (30m, 24h, 7d, 2w)")
	cmd.Flags().StringVar(&session, "session", "", "Only calls on this browser session id or alias name")
	cmd.Flags().IntVar(&limit, "limit", 50, "Maximum rows, newest first")
	cmd.Flags().StringVar(&dbPath, "db", "", "Local ledger database path (default: the CLI's data directory)")
	return cmd
}

func clipText(s string, n int) string {
	r := []rune(s)
	if len(r) <= n {
		return s
	}
	return string(r[:n-1]) + "…"
}
