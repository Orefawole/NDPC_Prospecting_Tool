# NDPC Prospecting Tool: Run Guide (Windows)

Plain-language steps for running the tool on Windows in VS Code. Also kept as a Claude Doc in the project.

## 1. Before you start

Run every command in the VS Code terminal (PowerShell), from the project folder. Every command starts with `python -m`, so it works without a virtual environment and without an Anthropic or Google key.

1. Open the project folder in VS Code, then open a terminal with **Terminal > New Terminal**.
2. Check you are in the right folder. The prompt should end in `NDPC_Prospecting_Tool>`. If not, run:

```powershell
cd "C:\Users\user\Documents\NDPC Prospecting tool\NDPC_Prospecting_Tool"
```

3. Get the latest version of the tool. Do this every time Claude tells you a fix was pushed:

```powershell
git pull
```

4. Install or update the packages the tool needs. Do this once, and again after a `git pull` that changes `requirements.txt`:

```powershell
python -m pip install -r requirements.txt
```

5. Create the database the first time. This is safe to run again.

```powershell
python -m prospect_intel init
```

You don't need a `.env` file to start. Without one, the tool uses OpenStreetMap to find businesses and its built-in rules to analyse them.

## 2. Running the tool, step by step

The tool works in four stages: find businesses, check them against NDPC, analyse and score them, then view or export the results. Steps 2.1 and 2.2 are the usual first run.

### 2.1 Test with one state (1 to 2 minutes)

```powershell
python -m prospect_intel discover --cities Lagos
```

Each step prints a line like `120 places in OpenStreetMap, 95 named businesses, 6 with websites`, then `saved 6 new`. You can name any state, or a big city such as Port Harcourt, Ibadan or Kano. Put names that contain a space in quotes, for example `--cities "Cross River"`.

### 2.2 Search all of Nigeria (20 to 40 minutes)

```powershell
python -m prospect_intel discover
```

This covers all 36 states and the FCT for Finance, Health and Insurance. Results are saved after each state and sector, so stopping it with Ctrl+C keeps what it has already found. Running it again does not create duplicates.

### 2.3 Optional: include businesses without a website

Most Nigerian businesses in OpenStreetMap don't list a website. This adds them too, often with a phone number:

```powershell
python -m prospect_intel discover --include-no-website
```

The tool can't collect evidence for these, so they score lower and their next step says to check them by hand.

### 2.4 Optional: limit to one sector

```powershell
python -m prospect_intel discover --sectors health
```

Use `finance`, `health` or `insurance`. You can combine this with `--cities`.

### 2.5 Optional: add your own list of businesses

1. Copy `data\businesses_template.csv`, then open the copy in Excel.
2. Fill in one row per business. `name` and `sector` are required. Also fill in `website` wherever you can, because the tool needs it to collect evidence.
3. Save it as CSV, then import it:

```powershell
python -m prospect_intel import-businesses data\my_businesses.csv
```

### 2.6 Load the NDPC register (recommended)

Without the register, every lead shows **Manual review**. With it, leads become **Verified**, **Unmatched** or **Manual review**.

The simplest way is to copy the register by hand:

1. Open [the NDPC register of Data Controllers/Processors of Major Importance](https://services.ndpc.gov.ng/repo/?flp=dcmi) in your browser.
2. Copy the table into Excel with the headings `name`, `category` and `year`.
3. Save it as `data\ndpc_dcmi.csv`, then import it:

```powershell
python -m prospect_intel import-ndpc data\ndpc_dcmi.csv --list dcmi
```

The tool can also read the register for you. This needs a one-time browser install and hasn't been tested yet:

```powershell
python -m pip install playwright
python -m playwright install chromium
python -m prospect_intel fetch-ndpc --list dcmi --out data\ndpc_dcmi.csv
python -m prospect_intel import-ndpc data\ndpc_dcmi.csv --list dcmi
```

### 2.7 Analyse and score the businesses

Start with 25 businesses to check the results look right. Each one takes a few seconds, because the tool waits politely between web pages.

```powershell
python -m prospect_intel run --limit 25 --no-claude
```

Then score the rest. Remove `--limit` to process everything that hasn't been scored yet:

```powershell
python -m prospect_intel run --no-claude
```

Other options:

- `--sector health` scores one sector only.
- `--refresh` re-scores businesses that were already scored, for example after you load the NDPC register.

### 2.8 Export and view the results

```powershell
python -m prospect_intel export
python -m streamlit run dashboard\app.py
```

Section 3 explains where these results land and how to use them.

### 2.9 Optional: try the tool on sample data

This loads 8 made-up businesses so you can explore the dashboard:

```powershell
python -m prospect_intel demo
```

The demo businesses go into the same database as your real ones, and their websites end in `.example`. To start fresh, delete `data\prospects.db` and run `python -m prospect_intel init` again.

## 3. Where the results are and how to open them

You can see your leads in two places: the dashboard in your browser, and a CSV file you can open in Excel or upload to Google Sheets. Both read the same database.

| What | Where | How to open it |
| --- | --- | --- |
| Dashboard | http://localhost:8501 | Run `python -m streamlit run dashboard\app.py`. It opens in your browser automatically; if not, paste the address. Leave the terminal open while you use it, and press Ctrl+C there to stop it. |
| Leads spreadsheet | `data\exports\leads.csv` in the project folder | Run `python -m prospect_intel export`, then double-click the file in File Explorer or in VS Code's file list. To save it somewhere else, add `--out C:\Users\user\Desktop\leads.csv`. |
| Database (everything) | `data\prospects.db` in the project folder | Used by the tool. Don't edit it. Copy it to make a backup. |

**Using the dashboard:**

- The filters on the left narrow the list by sector, state, NDPC status, likely tier, minimum score, or businesses with sensitive data.
- The table is sorted by score, highest first. Click a column heading to sort by it.
- **Download CSV** saves exactly what the filters show.
- Pick a business under **Lead detail** to see its summary, score breakdown, public contacts, gap signals and every piece of evidence with the page it came from.
- The **City** column shows the state for businesses found through OpenStreetMap.

**Reading a lead:**

- **Score (0 to 100):** 70 and above is high priority, 50 to 69 is medium, and under 50 is a watchlist. See `docs\SCORING.md` for how it is calculated.
- **NDPC status:** Verified means a matching register record was found. Unmatched means no record was found in the register you loaded, which is not proof the business is unregistered. Manual review means the match is uncertain, or no register is loaded.
- **Likely tier:** UHL, EHL or OHL is an estimate from the business type, based on the NDPC Guidance Notice.
- **Gap signals:** things not seen on the pages the tool visited, such as no privacy policy link. These are observations, not legal findings.
- **Next step:** the suggested action. Confirm anything about registration by hand before you contact a business.

## 4. Messages, errors and fixes

Most messages are normal. The table lists the ones you are likely to see, from the most common.

| You see | What it means | What to do |
| --- | --- | --- |
| `502 Bad Gateway` or `504 Gateway Timeout`, then `trying next server` | A free OpenStreetMap server is busy. The tool tries 4 servers, then retries after 20 and 60 seconds. | Nothing. Wait for the step to finish. |
| `could not get Bauchi finance: ...` | All 4 servers failed 3 times for that step. Everything else is still saved. | At the end, the tool prints the exact commands to rerun. Run them later, for example `python -m prospect_intel discover --cities "Bauchi" --sectors finance`. |
| `0 places in OpenStreetMap` for every step of a state | The state wasn't found in OpenStreetMap. | Send the output to Claude. |
| `... places ..., 0 with websites` | That state has places on the map, but none list a website. | Normal for many states. Add `--include-no-website` if you want them anyway. |
| `ModuleNotFoundError: No module named 'httpx'` (or another package) | A required package isn't installed. | Run `python -m pip install -r requirements.txt`. |
| `No module named prospect_intel` | The terminal isn't in the project folder. | Run the `cd` command from section 1, then try again. |
| `running scripts is disabled on this system` | Windows is blocking a script, usually a virtual environment's `Activate.ps1`. You don't need it with the `python -m` commands in this guide. | Ignore it. If you do want scripts allowed, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once and answer Y. |
| `'streamlit' is not recognized` | Windows can't find the streamlit program. | Use `python -m streamlit run dashboard\app.py` instead. |
| `'python' is not recognized` | Python isn't on your PATH. | Try `py` in place of `python` in every command, or reinstall Python with **Add python.exe to PATH** ticked. |
| `GOOGLE_PLACES_API_KEY is not set` | Google search was requested without a key. | Leave out `--source google`. OpenStreetMap is the default. |
| `git pull` says your local changes would be overwritten | You edited a file that Claude also changed. | Run `git stash`, then `git pull`. |

### Adding a Claude key later

With an Anthropic key, Claude reads each website and privacy policy closely and writes better summaries. To add one:

1. Sign up at [console.anthropic.com](https://console.anthropic.com), add credit under **Billing**, and create a key under **API Keys**.
2. In the project folder, run `Copy-Item .env.example .env`, then open `.env` in VS Code.
3. Paste your key after `ANTHROPIC_API_KEY=` and save the file. Never share the key or send it in chat.
4. Re-analyse your leads with Claude. Note that `--no-claude` is left out:

```powershell
python -m prospect_intel run --refresh
```

The dashboard shows `claude` or `heuristic` next to each summary, so you can see which method produced it.

### Quick reference

```powershell
git pull
python -m pip install -r requirements.txt
python -m prospect_intel discover --cities Lagos
python -m prospect_intel discover
python -m prospect_intel import-ndpc data\ndpc_dcmi.csv --list dcmi
python -m prospect_intel run --no-claude
python -m prospect_intel export
python -m streamlit run dashboard\app.py
```
