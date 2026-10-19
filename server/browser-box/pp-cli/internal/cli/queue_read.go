// Copyright 2026 jbellsolutions and contributors. Licensed under Apache-2.0. See LICENSE.
// pp:data-source live

package cli

import (
	"errors"
	"fmt"
	"strings"

	"github.com/spf13/cobra"

	"browser-box-pp-cli/internal/cliutil"
)

func init() {
	registerNovelCommand(func(root *cobra.Command, flags *rootFlags) {
		queueCmd, _, err := root.Find([]string{"queue"})
		if err == nil && queueCmd != root {
			addNovelCommandIfAbsent(queueCmd, newQueueReadCmd(flags))
		}
	})
}

func newQueueReadCmd(flags *rootFlags) *cobra.Command {
	var file, backoff string
	var retries int
	var withText bool

	cmd := &cobra.Command{
		Use:   "read [url...]",
		Short: "Read many pages in the box's browser, one at a time, retrying when the box answers busy",
		Long: strings.Trim(`
Reads each URL in order through the box's browser. A busy refusal is
retried after a growing wait (--backoff, doubled each time, up to --retries);
any other refusal, such as a private address, fails that URL only. Every page
lands in the local cache, so 'cache <url>' and 'find' work on them afterwards.

Output is one row per URL with title, final URL and text length; add --text to
include each page's text. Exit 0 when at least one page was read.`, "\n"),
		Example: strings.Trim(`
  browser-box-pp-cli queue read https://example.com https://news.ycombinator.com --agent
  browser-box-pp-cli queue read --file urls.txt --retries 5 --backoff 20s
  cat urls.txt | browser-box-pp-cli queue read --file - --agent --select results.url,results.ok`, "\n"),
		Annotations: map[string]string{"pp:data-source": "live", "pp:happy-args": "url=https://example.com"},
		RunE: func(cmd *cobra.Command, args []string) error {
			if len(args) == 0 && cmd.Flags().NFlag() == 0 {
				return cmd.Help()
			}
			if dryRunOK(flags) {
				return writeDryRun(cmd.OutOrStdout(), flags, "queue read")
			}
			wait, err := cliutil.ParseDurationLoose(backoff)
			if err != nil || wait < 0 {
				return usageErr(fmt.Errorf("--backoff %q: use a duration like 10s or 1m", backoff))
			}
			if retries < 0 {
				return usageErr(fmt.Errorf("--retries must be 0 or more"))
			}
			urls := append([]string{}, args...)
			if file != "" {
				fromFile, err := readURLList(cmd.InOrStdin(), file)
				if err != nil {
					return usageErr(err)
				}
				urls = append(urls, fromFile...)
			}
			if len(urls) == 0 {
				_ = cmd.Usage()
				return usageErr(fmt.Errorf("give URLs as arguments or with --file"))
			}
			view := queueView{Results: make([]queuedRead, 0, len(urls))}
			if cliutil.IsDogfoodEnv() && len(urls) > 1 {
				view.Note = fmt.Sprintf("test harness: read the first of %d URLs only", len(urls))
				urls, retries = urls[:1], 0
			}
			c, err := flags.newClient()
			if err != nil {
				return err
			}
			for i, u := range urls {
				row := readWithRetry(cmd, c, u, retries, wait)
				if !withText {
					row.Text = ""
				}
				view.Results = append(view.Results, row)
				if row.OK {
					view.Read++
				} else {
					view.Failed++
				}
				if !flags.quiet && wantsHumanTable(cmd.OutOrStdout(), flags) {
					mark := "ok  "
					if !row.OK {
						mark = "FAIL"
					}
					fmt.Fprintf(cmd.ErrOrStderr(), "[%d/%d] %s %s\n", i+1, len(urls), mark, u)
				}
			}
			if view.Failed > 0 {
				fmt.Fprintf(cmd.ErrOrStderr(), "warning: %d of %d URLs failed; see each row's error\n", view.Failed, len(view.Results))
			}
			if !wantsHumanTable(cmd.OutOrStdout(), flags) {
				if err := printJSONFiltered(cmd.OutOrStdout(), view, flags); err != nil {
					return err
				}
			} else {
				rows := make([][]string, 0, len(view.Results))
				for _, r := range view.Results {
					detail := clipText(r.Title, 50)
					if !r.OK {
						detail = clipText(r.Error, 70)
					}
					rows = append(rows, []string{fmt.Sprint(r.OK), fmt.Sprint(r.Attempts), clipText(r.URL, 50), detail})
				}
				if err := flags.printTable(cmd, []string{"OK", "TRIES", "URL", "TITLE / ERROR"}, rows); err != nil {
					return err
				}
			}
			if view.Read == 0 {
				return apiErr(errors.New("no URL could be read"))
			}
			return nil
		},
	}
	cmd.Flags().StringVar(&file, "file", "", "Read URLs from this file, one per line ('-' for stdin; blank lines and # comments skipped)")
	cmd.Flags().IntVar(&retries, "retries", 3, "Retries per URL while the box answers busy")
	cmd.Flags().StringVar(&backoff, "backoff", "10s", "First wait before retrying a busy refusal; doubles each retry")
	cmd.Flags().BoolVar(&withText, "text", false, "Include each page's text in the output (it is always cached locally)")
	return cmd
}
