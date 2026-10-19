// Copyright 2026 jbellsolutions and contributors. Licensed under Apache-2.0. See LICENSE.
// pp:data-source computed

package cli

import (
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/spf13/cobra"

	"browser-box-pp-cli/internal/ledger"
	"browser-box-pp-cli/internal/store"
)

type driftView struct {
	Now        string          `json:"now"`
	PreviousAt string          `json:"previous_at,omitempty"`
	Changes    []ledger.Change `json:"changes"`
	Note       string          `json:"note,omitempty"`
}

func newNovelDriftCmd(flags *rootFlags) *cobra.Command {
	cmd := &cobra.Command{
		Use:   "drift",
		Short: "See only what changed on the box since you last looked.",
		Long: strings.Trim(`
Calls status on the box, compares it with the last status this CLI stored,
and prints only the differences: components that went up or down, tools that
started or stopped working and why.
Recent calls and spend are ignored because they change on every call. The new
status is stored, so the next drift compares against this one.

Use this command to see what changed on the box since the last check. Do NOT
use this command for a one-shot health check; use 'status' or 'doctor'
instead.`, "\n"),
		Example: strings.Trim(`
  browser-box-pp-cli drift --agent
  browser-box-pp-cli drift --agent --select changes`, "\n"),
		Annotations: map[string]string{"mcp:read-only": "true", "pp:data-source": "computed"},
		RunE: func(cmd *cobra.Command, args []string) error {
			if dryRunOK(flags) {
				return writeDryRun(cmd.OutOrStdout(), flags, "drift")
			}
			var previous *store.Snapshot
			db, found, err := openLedger(cmd.Context(), "")
			if err != nil {
				return err
			}
			if found {
				previous, err = db.LatestSnapshot(cmd.Context())
				_ = db.Close()
				if err != nil {
					return fmt.Errorf("reading the last status snapshot: %w", err)
				}
			}
			c, err := flags.newClient()
			if err != nil {
				return err
			}
			// The ledger transport stores this status as the new snapshot.
			current, err := c.GetNoCache(cmd.Context(), "/api/v1/status", nil)
			if err != nil {
				return classifyAPIError(cmd.OutOrStdout(), err, flags)
			}
			if os.Getenv("BROWSER_BOX_NO_LEDGER") != "" {
				// No transport recording: store the baseline here, or the next drift has none.
				if db, err := openLedgerForWrite(cmd.Context(), ""); err == nil {
					call, _ := ledger.Build("status", nil, current, 200, 0, time.Now())
					if err := db.RecordCall(cmd.Context(), call, nil, current); err != nil {
						fmt.Fprintf(cmd.ErrOrStderr(), "warning: status baseline not stored: %v\n", err)
					}
					_ = db.Close()
				}
			}
			view := driftView{Now: time.Now().UTC().Format(time.RFC3339), Changes: make([]ledger.Change, 0)}
			if previous == nil {
				view.Note = "no earlier status was stored; this one is now the baseline for the next drift"
			} else {
				view.PreviousAt = previous.At
				view.Changes = ledger.DiffStatus(previous.Data, current)
			}
			if !wantsHumanTable(cmd.OutOrStdout(), flags) {
				return printJSONFiltered(cmd.OutOrStdout(), view, flags)
			}
			switch {
			case view.Note != "":
				fmt.Fprintln(cmd.OutOrStdout(), view.Note)
			case len(view.Changes) == 0:
				fmt.Fprintf(cmd.OutOrStdout(), "Nothing changed since %s.\n", view.PreviousAt)
			default:
				rows := make([][]string, 0, len(view.Changes))
				for _, ch := range view.Changes {
					rows = append(rows, []string{ch.What, ch.Before, ch.After})
				}
				fmt.Fprintf(cmd.OutOrStdout(), "Changed since %s:\n", view.PreviousAt)
				return flags.printTable(cmd, []string{"WHAT", "BEFORE", "NOW"}, rows)
			}
			return nil
		},
	}
	return cmd
}
