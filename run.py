"""
run.py -- build the portfolio dashboard and serve it at http://localhost:8000

    python run.py

Rebuilds the dashboard from the studies' outputs (seconds), then serves
dashboard/ on localhost and opens it in Chrome. Ctrl+C stops the server.
Set RERUN_STUDIES = True to regenerate every study from cached data first --
slow: the Monte Carlo steps alone take ~40 min. The dashboard shows a warning
banner when outputs were produced under a different configuration than the
current one (common/manifest.py), which is the cue to re-run.

To serve the last build without rebuilding:
    python -m http.server 8000 --bind 127.0.0.1 -d dashboard
"""
import functools
import http.server
import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

RERUN_STUDIES = False
PORT = 8000
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

SUITE = Path(__file__).resolve().parent

STUDIES = [
    ("efficient_core", ["ec_data.py", "ec_validate.py", "ec_analysis.py",
                        "ec_montecarlo.py", "ec_charts.py", "ec_ntsd.py"]),
    ("scv_leverage", ["kd_phase2_validate.py", "kd_phase346_removal.py",
                      "kd_phase5_control.py", "kd_phase8_diag.py",
                      "kd_phase79_mc.py", "kd_phase12_cluster.py",
                      "kd_phase12_context.py", "kd_phase13_optlev.py",
                      "kd_phase14_fractions.py",
                      "kd_phase11_validate.py", "kd_charts.py"]),
    ("common", ["validate_leverage.py"]),
    ("reconstructions", ["recon.py"]),
    ("testfolio_check", ["tf_verify.py", "tf_compare.py"]),
]
ALWAYS = [
    ("dashboard", ["build_data.py", "build_dashboard.py"]),
]


def run(folder: str, script: str) -> None:
    print(f"\n=== {folder}/{script}", flush=True)
    t0 = time.time()
    subprocess.run([sys.executable, script], cwd=SUITE / folder, check=True)
    print(f"--- {script} done in {time.time() - t0:,.0f}s", flush=True)


def serve() -> None:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler,
                                directory=str(SUITE / "dashboard"))
    # 127.0.0.1 only: reachable from this machine, not from the network.
    with http.server.ThreadingHTTPServer(("127.0.0.1", PORT), handler) as httpd:
        url = f"http://localhost:{PORT}/"
        print(f"\nserving {url}   (Ctrl+C to stop)", flush=True)
        if os.path.exists(CHROME):
            subprocess.Popen([CHROME, url])
        else:
            webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped")


def main() -> None:
    for folder, scripts in (STUDIES if RERUN_STUDIES else []) + ALWAYS:
        for s in scripts:
            run(folder, s)
    serve()


if __name__ == "__main__":
    main()
