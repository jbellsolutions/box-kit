"""Pure-Python checks against browser-use 0.13.11 (no browser, no network)."""
import json, os, tempfile
os.environ.setdefault("ANONYMIZED_TELEMETRY", "false"); os.environ.setdefault("BROWSER_USE_SETUP_LOGGING", "false")
from browser_use import Browser, BrowserProfile, BrowserSession
out = {}
X = "ws://127.0.0.1:1/"
out["wrapper_form_is_local"] = BrowserSession(browser_profile=BrowserProfile(cdp_url=X, is_local=False)).is_local
out["direct_form_is_local"] = Browser(cdp_url=X).is_local
out["direct_form_explicit_false_is_local"] = BrowserSession(cdp_url=X, is_local=False).is_local
base = tempfile.mkdtemp(prefix="fleetspike-")
for name in ("chrome-profile-1", "profile-1", "Chrome"):
    p = os.path.join(base, name)
    os.makedirs(p, exist_ok=True)
    prof = BrowserProfile(user_data_dir=p)
    out[f"user_data_dir[{name}]"] = {"given": p, "effective": str(prof.user_data_dir), "same": str(prof.user_data_dir) == p}
prof = BrowserProfile(user_data_dir=os.path.join(base, "profile-2"), channel="chrome")
out["user_data_dir[profile-2, channel=chrome]"] = {"effective_is_temp": "browser-use-user-data-dir-" in str(prof.user_data_dir)}
d = BrowserProfile()
out["defaults"] = {"permissions": d.permissions, "accept_downloads": d.accept_downloads, "auto_download_pdfs": d.auto_download_pdfs,
                   "user_data_dir": str(d.user_data_dir) if d.user_data_dir else None, "storage_state": d.storage_state,
                   "keep_alive": d.keep_alive, "headless": d.headless, "enable_default_extensions": d.enable_default_extensions,
                   "captcha_solver": d.captcha_solver, "downloads_path_is_local_tmp": str(d.downloads_path).startswith(tempfile.gettempdir()),
                   "highlight_elements": d.highlight_elements, "wait_between_actions": d.wait_between_actions,
                   "minimum_wait_page_load_time": d.minimum_wait_page_load_time}
print(json.dumps(out, indent=1, default=str))
