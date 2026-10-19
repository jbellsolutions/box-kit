// Copyright 2026 jbellsolutions and contributors. Licensed under Apache-2.0. See LICENSE.

// Package ledger turns one browser-box HTTP exchange into the rows this CLI
// keeps locally: a call record, the page a fetch/read returned, and status
// snapshots. The box itself remembers only its last 10 calls; everything
// here is what the CLI remembers for it. Pure functions, no IO.
package ledger

import (
	"encoding/json"
	"fmt"
	"sort"
	"strings"
	"time"
)

// TimeFormat is fixed-width so stored timestamps compare correctly as text.
const TimeFormat = "2006-01-02T15:04:05.000Z"

const maxArg = 500

// Call is one request to the box, successful or not.
type Call struct {
	At         time.Time       `json:"at"`
	Tool       string          `json:"tool"`
	Summary    string          `json:"summary"`
	Args       json.RawMessage `json:"args"`
	HTTPStatus int             `json:"http_status"`
	OK         bool            `json:"ok"`
	Status     string          `json:"status"`
	Error      string          `json:"error,omitempty"`
	DurationMS int64           `json:"duration_ms"`
	CostUSD    *float64        `json:"cost_usd,omitempty"`
	SessionID  string          `json:"session_id,omitempty"`
	URL        string          `json:"url,omitempty"`
}

// Page is the text a fetch or read brought back.
type Page struct {
	URL      string   `json:"url"`
	FinalURL string   `json:"final_url"`
	Title    string   `json:"title"`
	Text     string   `json:"text"`
	Links    []string `json:"links"`
	Via      string   `json:"via"`
}

// ToolFromPath names the box tool an HTTP request calls, or ok=false for
// anything that is not a tool call (the OpenAPI document, other paths). The
// box may sit under a path prefix, so the last /api/v1/ segment counts.
func ToolFromPath(method, path string) (tool string, ok bool) {
	path = strings.TrimRight(path, "/")
	i := strings.LastIndex(path, "/api/v1/")
	if i < 0 {
		return "", false
	}
	rest := path[i+len("/api/v1/"):]
	if rest == "" || strings.Contains(rest, "/") {
		return "", false
	}
	switch {
	case method == "GET" && (rest == "status" || rest == "tools"):
		return rest, true
	case method == "POST" && rest != "status" && rest != "tools":
		return rest, true
	}
	return "", false
}

// Build derives the call record, and the page when the call returned one.
// req and resp are the raw JSON bodies; either may be empty or not JSON.
func Build(tool string, req, resp []byte, httpStatus int, took time.Duration, at time.Time) (Call, *Page) {
	args := objectOf(req)
	out := objectOf(resp)
	call := Call{
		At:         at.UTC(),
		Tool:       tool,
		Args:       redactedArgs(tool, args),
		HTTPStatus: httpStatus,
		DurationMS: took.Milliseconds(),
	}
	call.Error = str(out["error"])
	call.Status = str(out["status"])
	reportedFailure := out["ok"] == false || failedStatus[call.Status]
	call.OK = httpStatus >= 200 && httpStatus < 300 && call.Error == "" && !reportedFailure
	if call.Status == "" || isNumber(out["status"]) {
		call.Status = "ok"
		if !call.OK {
			call.Status = "error"
			if IsLaneBusy(call.Error) {
				call.Status = "lane_busy"
			} else if httpStatus == 422 {
				call.Status = "refused"
			}
		}
	}
	if cost, ok := number(out["estimated_cost_usd"]); ok {
		call.CostUSD = &cost
	}
	call.SessionID = firstNonEmpty(str(args["session_id"]), str(out["session_id"]))
	call.URL = firstNonEmpty(str(args["url"]), str(out["final_url"]), str(out["url"]))
	call.Summary = summarize(tool, args)

	if !call.OK || (tool != "fetch" && tool != "read") {
		return call, nil
	}
	text := str(out["text"])
	if strings.TrimSpace(text) == "" {
		return call, nil
	}
	page := &Page{
		URL:      str(args["url"]),
		FinalURL: firstNonEmpty(str(out["final_url"]), str(args["url"])),
		Title:    str(out["title"]),
		Text:     text,
		Links:    strings_(out["links"]),
		Via:      tool,
	}
	if page.URL == "" {
		page.URL = page.FinalURL
	}
	return call, page
}

// failedStatus are the statuses act and task answer with HTTP 200 when the
// work did not get done. needs_clarification and needs_confirmation are not
// failures: they wait for the caller's answer.
var failedStatus = map[string]bool{
	"failed": true, "incomplete": true, "timed_out": true, "timeout": true,
	"cancelled": true, "stopped": true, "error": true,
}

// UsesBrowserSession reports whether a tool runs in the box's browser, and so
// under whatever session is open there.
func UsesBrowserSession(tool string) bool {
	return tool == "read" || tool == "act" || tool == "task"
}

// IsLaneBusy reports whether an error is one of the box's busy refusals, the
// only refusals worth retrying unchanged: a saved session's browser in use by
// another call, or an Orgo computer's lane held by another job.
func IsLaneBusy(msg string) bool {
	m := strings.ToLower(msg)
	if strings.Contains(m, "lane") && (strings.Contains(m, "held") || strings.Contains(m, "busy")) {
		return true
	}
	return strings.Contains(m, "is busy") && strings.Contains(m, "try again")
}

// WithoutScreenshot drops screenshot_base64 from a JSON object so the ledger
// never stores images. Non-objects come back unchanged.
func WithoutScreenshot(resp []byte) []byte {
	obj := objectOf(resp)
	if _, has := obj["screenshot_base64"]; !has {
		return resp
	}
	delete(obj, "screenshot_base64")
	out, err := json.Marshal(obj)
	if err != nil {
		return resp
	}
	return out
}

// Change is one difference between two status snapshots.
type Change struct {
	What   string `json:"what"`
	Before string `json:"before"`
	After  string `json:"after"`
}

// DiffStatus compares two status results by what matters to a caller: which
// components are up, which tools work, why the others do not, and the lane.
// It ignores recent_calls and spend, which change on every call.
func DiffStatus(prev, cur []byte) []Change {
	a, b := objectOf(prev), objectOf(cur)
	changes := make([]Change, 0)

	ca, cb := components(a["components"]), components(b["components"])
	for _, name := range unionKeys(ca, cb) {
		before, after := ca[name], cb[name]
		if before != after {
			changes = append(changes, Change{What: "component " + name, Before: orAbsent(before), After: orAbsent(after)})
		}
	}

	wa, wb := set(strings_(a["tools_working_now"])), set(strings_(b["tools_working_now"]))
	for _, t := range unionKeys(wa, wb) {
		if wa[t] != wb[t] {
			changes = append(changes, Change{What: "tool " + t, Before: working(wa[t]), After: working(wb[t])})
		}
	}

	ua, ub := unavailable(a["tools_unavailable"]), unavailable(b["tools_unavailable"])
	for _, k := range unionKeys(ua, ub) {
		if ua[k] != ub[k] {
			changes = append(changes, Change{What: "unavailable " + k, Before: orAbsent(ua[k]), After: orAbsent(ub[k])})
		}
	}

	la, lb := laneState(str(a["browser_lane"])), laneState(str(b["browser_lane"]))
	if la != lb {
		changes = append(changes, Change{What: "browser lane", Before: orAbsent(la), After: orAbsent(lb)})
	}
	return changes
}

func summarize(tool string, args map[string]any) string {
	switch tool {
	case "fetch", "read":
		return str(args["url"])
	case "session":
		return strings.TrimSpace(firstNonEmpty(str(args["action"]), "create") + " " + str(args["session_id"]))
	case "act":
		if p := str(args["pick"]); p != "" {
			return "pick: " + clip(p, 120)
		}
		if c, ok := args["confirm"]; ok {
			return fmt.Sprintf("confirm: %v", c)
		}
		return clip(str(args["command"]), 160)
	case "task":
		if b, _ := args["cancel"].(bool); b {
			return "cancel"
		}
		return clip(str(args["goal"]), 160)
	case "computer":
		action := str(args["action"])
		switch action {
		case "click", "scroll":
			return fmt.Sprintf("%s %v,%v", action, args["x"], args["y"])
		case "key":
			return "key " + str(args["key"])
		case "bash":
			return "bash " + clip(str(args["command"]), 120)
		case "type":
			return "type"
		}
		return action
	}
	return ""
}

// redactedArgs keeps the request for the ledger, minus what should not sit in
// a local database: text typed on a desktop (it may be a password) and
// anything very long.
func redactedArgs(tool string, args map[string]any) json.RawMessage {
	if len(args) == 0 {
		return json.RawMessage(`{}`)
	}
	clean := make(map[string]any, len(args))
	for k, v := range args {
		if s, ok := v.(string); ok {
			if tool == "computer" && k == "text" {
				clean[k] = fmt.Sprintf("[redacted %d chars]", len(s))
				continue
			}
			clean[k] = clip(s, maxArg)
			continue
		}
		clean[k] = v
	}
	out, err := json.Marshal(clean)
	if err != nil {
		return json.RawMessage(`{}`)
	}
	return out
}

func components(v any) map[string]string {
	out := map[string]string{}
	list, _ := v.([]any)
	for _, item := range list {
		c, _ := item.(map[string]any)
		name := str(c["name"])
		if name == "" {
			continue
		}
		state := "down"
		if up, _ := c["up"].(bool); up {
			state = "up"
		} else if configured, ok := c["configured"].(bool); ok && !configured {
			state = "not configured"
		}
		out[name] = state
	}
	return out
}

func unavailable(v any) map[string]string {
	out := map[string]string{}
	list, _ := v.([]any)
	for _, item := range list {
		u, _ := item.(map[string]any)
		key := str(u["tool"])
		if s := str(u["surface"]); s != "" {
			key += "(" + s + ")"
		}
		if key != "" {
			out[key] = clip(str(u["reason"]), 160)
		}
	}
	return out
}

// laneState reduces the lane detail to free/busy: the holder text changes
// every call and would make drift report noise.
func laneState(detail string) string {
	d := strings.ToLower(strings.TrimSpace(detail))
	switch {
	case d == "":
		return ""
	case strings.HasPrefix(d, "busy"):
		return "busy"
	case strings.HasPrefix(d, "free"):
		return "free"
	}
	return clip(detail, 80)
}

func working(on bool) string {
	if on {
		return "working"
	}
	return "not working"
}

func orAbsent(s string) string {
	if s == "" {
		return "(absent)"
	}
	return s
}

func set(items []string) map[string]bool {
	out := make(map[string]bool, len(items))
	for _, i := range items {
		out[i] = true
	}
	return out
}

func unionKeys[V any](a, b map[string]V) []string {
	seen := map[string]bool{}
	keys := make([]string, 0, len(a)+len(b))
	for _, m := range []map[string]V{a, b} {
		for k := range m {
			if !seen[k] {
				seen[k] = true
				keys = append(keys, k)
			}
		}
	}
	sort.Strings(keys)
	return keys
}

func objectOf(b []byte) map[string]any {
	var m map[string]any
	if len(b) == 0 || json.Unmarshal(b, &m) != nil || m == nil {
		return map[string]any{}
	}
	return m
}

func str(v any) string {
	s, _ := v.(string)
	return s
}

func isNumber(v any) bool {
	_, ok := v.(float64)
	return ok
}

func number(v any) (float64, bool) {
	f, ok := v.(float64)
	return f, ok
}

func strings_(v any) []string {
	list, _ := v.([]any)
	out := make([]string, 0, len(list))
	for _, item := range list {
		if s, ok := item.(string); ok && s != "" {
			out = append(out, s)
		}
	}
	return out
}

func firstNonEmpty(values ...string) string {
	for _, v := range values {
		if v != "" {
			return v
		}
	}
	return ""
}

func clip(s string, limit int) string {
	if len(s) <= limit {
		return s
	}
	return s[:limit] + "…"
}
