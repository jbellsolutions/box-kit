// Copyright 2026 jbellsolutions and contributors. Licensed under Apache-2.0. See LICENSE.
// pp:data-source local

package cli

import (
	"fmt"
	"regexp"
	"strings"
	"time"

	"github.com/spf13/cobra"

	"browser-box-pp-cli/internal/ledger"
	"browser-box-pp-cli/internal/store"
)

var aliasName = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$`)

const aliasLong = `
Session ids from 'session --action create' are opaque. While a session is open,
the box's browser uses its cookies for every later read, act and task: those
tools take no session id. An alias names the session, and what it is logged
into, so you can tell later which session is which and release the right one:
'browser-box-pp-cli session --action release --session-id "$(browser-box-pp-cli alias get crm)"'.
'history --session <alias>' shows the calls made while it was the open session.

Use this command to name a persistent session_id and look it up later. Do NOT
use this command to create or release a session; use 'session' instead.

Bare 'alias' lists every alias.`

func newNovelAliasCmd(flags *rootFlags) *cobra.Command {
	var dbPath string
	cmd := &cobra.Command{
		Use:   "alias",
		Short: "Name a logged-in browser session so you can tell later which one it is and release it.",
		Long:  strings.Trim(aliasLong, "\n"),
		Example: strings.Trim(`
  browser-box-pp-cli alias --agent
  browser-box-pp-cli alias set crm
  browser-box-pp-cli alias set crm sess_8f2c --note "HubSpot, logged in"
  browser-box-pp-cli alias get crm --agent`, "\n"),
		Annotations: map[string]string{"pp:data-source": "local"},
		RunE: func(cmd *cobra.Command, args []string) error {
			if dryRunOK(flags) {
				return writeDryRun(cmd.OutOrStdout(), flags, "alias list")
			}
			return listAliases(cmd, flags, dbPath)
		},
	}
	cmd.PersistentFlags().StringVar(&dbPath, "db", "", "Local ledger database path (default: the CLI's data directory)")
	cmd.AddCommand(newAliasSetCmd(flags, &dbPath), newAliasGetCmd(flags, &dbPath), newAliasListCmd(flags, &dbPath), newAliasRmCmd(flags, &dbPath))
	return cmd
}

func newAliasSetCmd(flags *rootFlags, dbPath *string) *cobra.Command {
	var note string
	cmd := &cobra.Command{
		Use:   "set <name> [session_id]",
		Short: "Name a session; without an id, names the session this CLI created most recently",
		Example: strings.Trim(`
  browser-box-pp-cli alias set crm
  browser-box-pp-cli alias set crm sess_8f2c --note "HubSpot, logged in"`, "\n"),
		Annotations: map[string]string{"pp:happy-args": "name=example;session_id=sess_example"},
		RunE: func(cmd *cobra.Command, args []string) error {
			if len(args) == 0 && cmd.Flags().NFlag() == 0 {
				return cmd.Help()
			}
			if dryRunOK(flags) {
				return writeDryRun(cmd.OutOrStdout(), flags, "alias set")
			}
			if len(args) == 0 || len(args) > 2 {
				_ = cmd.Usage()
				return usageErr(fmt.Errorf("give a name, and optionally a session id"))
			}
			name := args[0]
			if !aliasName.MatchString(name) {
				return usageErr(fmt.Errorf("alias %q: use letters, digits, '.', '_' or '-' (up to 64)", name))
			}
			db, err := openLedgerForWrite(cmd.Context(), *dbPath)
			if err != nil {
				return err
			}
			defer db.Close()
			sessionID := ""
			if len(args) == 2 {
				sessionID = strings.TrimSpace(args[1])
			} else {
				if sessionID, err = db.LastCreatedSession(cmd.Context()); err != nil {
					return err
				}
				if sessionID == "" {
					return usageErr(fmt.Errorf("no session was created through this CLI yet: give the session id, or run 'browser-box-pp-cli session --action create' first"))
				}
			}
			if sessionID == "" {
				return usageErr(fmt.Errorf("the session id is empty"))
			}
			a := store.Alias{Name: name, SessionID: sessionID, Note: note, UpdatedAt: time.Now().UTC().Format(ledger.TimeFormat)}
			if err := db.SetAlias(cmd.Context(), a); err != nil {
				return fmt.Errorf("saving alias: %w", err)
			}
			if !wantsHumanTable(cmd.OutOrStdout(), flags) {
				return printJSONFiltered(cmd.OutOrStdout(), a, flags)
			}
			fmt.Fprintf(cmd.OutOrStdout(), "%s → %s\n", a.Name, a.SessionID)
			return nil
		},
	}
	cmd.Flags().StringVar(&note, "note", "", "What this session is logged into, for your future self")
	return cmd
}

func newAliasGetCmd(flags *rootFlags, dbPath *string) *cobra.Command {
	return &cobra.Command{
		Use:     "get <name>",
		Short:   "Print the session id an alias names (exit 3 when there is no such alias)",
		Example: "  browser-box-pp-cli alias get crm --agent --select session_id",
		Annotations: map[string]string{
			"mcp:read-only":          "true",
			"pp:typed-exit-codes":    "0,3",
			"pp:no-error-path-probe": "true",
		},
		RunE: func(cmd *cobra.Command, args []string) error {
			if len(args) == 0 && cmd.Flags().NFlag() == 0 {
				return cmd.Help()
			}
			if dryRunOK(flags) {
				return writeDryRun(cmd.OutOrStdout(), flags, "alias get")
			}
			if len(args) != 1 {
				_ = cmd.Usage()
				return usageErr(fmt.Errorf("give exactly one alias name"))
			}
			var a *store.Alias
			db, found, err := openLedger(cmd.Context(), *dbPath)
			if err != nil {
				return err
			}
			if found {
				defer db.Close()
				if a, err = db.GetAlias(cmd.Context(), args[0]); err != nil {
					return err
				}
			}
			if a == nil {
				return notFoundErr(fmt.Errorf("no alias %q: 'browser-box-pp-cli alias list' shows the ones you have", args[0]))
			}
			if !wantsHumanTable(cmd.OutOrStdout(), flags) {
				return printJSONFiltered(cmd.OutOrStdout(), a, flags)
			}
			fmt.Fprintln(cmd.OutOrStdout(), a.SessionID)
			return nil
		},
	}
}

func newAliasListCmd(flags *rootFlags, dbPath *string) *cobra.Command {
	return &cobra.Command{
		Use:         "list",
		Short:       "List every session alias",
		Example:     "  browser-box-pp-cli alias list --agent",
		Annotations: map[string]string{"mcp:read-only": "true"},
		RunE: func(cmd *cobra.Command, args []string) error {
			if dryRunOK(flags) {
				return writeDryRun(cmd.OutOrStdout(), flags, "alias list")
			}
			return listAliases(cmd, flags, *dbPath)
		},
	}
}

func newAliasRmCmd(flags *rootFlags, dbPath *string) *cobra.Command {
	return &cobra.Command{
		Use:     "rm <name>",
		Short:   "Forget an alias (the browser session itself is not touched)",
		Example: "  browser-box-pp-cli alias rm crm",
		RunE: func(cmd *cobra.Command, args []string) error {
			if len(args) == 0 && cmd.Flags().NFlag() == 0 {
				return cmd.Help()
			}
			if dryRunOK(flags) {
				return writeDryRun(cmd.OutOrStdout(), flags, "alias rm")
			}
			if len(args) != 1 {
				_ = cmd.Usage()
				return usageErr(fmt.Errorf("give exactly one alias name"))
			}
			db, err := openLedgerForWrite(cmd.Context(), *dbPath)
			if err != nil {
				return err
			}
			defer db.Close()
			removed, err := db.DeleteAlias(cmd.Context(), args[0])
			if err != nil {
				return err
			}
			result := map[string]any{"name": args[0], "removed": removed}
			if !wantsHumanTable(cmd.OutOrStdout(), flags) {
				return printJSONFiltered(cmd.OutOrStdout(), result, flags)
			}
			if removed {
				fmt.Fprintf(cmd.OutOrStdout(), "removed %s\n", args[0])
			} else {
				fmt.Fprintf(cmd.OutOrStdout(), "no alias %s\n", args[0])
			}
			return nil
		},
	}
}

func listAliases(cmd *cobra.Command, flags *rootFlags, dbPath string) error {
	aliases := make([]store.Alias, 0)
	db, found, err := openLedger(cmd.Context(), dbPath)
	if err != nil {
		return err
	}
	if found {
		defer db.Close()
		if aliases, err = db.Aliases(cmd.Context()); err != nil {
			return err
		}
	}
	if !wantsHumanTable(cmd.OutOrStdout(), flags) {
		return printJSONFiltered(cmd.OutOrStdout(), aliases, flags)
	}
	if len(aliases) == 0 {
		fmt.Fprintln(cmd.OutOrStdout(), "No aliases yet: 'browser-box-pp-cli alias set <name>' after creating a session.")
		return nil
	}
	rows := make([][]string, 0, len(aliases))
	for _, a := range aliases {
		rows = append(rows, []string{a.Name, a.SessionID, a.UpdatedAt[:19], a.Note})
	}
	return flags.printTable(cmd, []string{"NAME", "SESSION", "UPDATED (UTC)", "NOTE"}, rows)
}
