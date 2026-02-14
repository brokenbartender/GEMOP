# 💰 Money Missions: Revenue Template Bank

Use these templates to quickly launch high-value commercial tasks. Copy and paste them into the Dashboard.

---

## 🕷️ Template 1: The Scraper (Lead Generation)
**Goal:** Extract business leads from a target URL.

**Prompt:**
> "I need to generate a business lead list from [TARGET URL]. 
> 1. Use Playwright to scrape the following fields: Business Name, Contact Email, and Website URL. 
> 2. Implement anti-bot measures including random user-agent rotation and human-like delays. 
> 3. Clean the data to remove duplicates and invalid email formats. 
> 4. Save the final list to `leads_export.csv`."

---

## 🛠️ Template 2: The Converter (Micro-SaaS)
**Goal:** Build a functional file conversion utility.

**Prompt:**
> "Build a Streamlit-based Micro-SaaS tool for file conversion.
> 1. Create a drag-and-drop interface that accepts PDF files.
> 2. Use `pdfplumber` or `pandas` to extract tabular data from the PDF.
> 3. Provide a 'Download as Excel' button for the processed data.
> 4. Style the UI using Material Design principles for a professional look.
> 5. Save the code to `app_converter.py`."

---

## 📈 Template 3: The Analyst (Data Arbitrage)
**Goal:** Generate insights from financial market data.

**Prompt:**
> "Generate a trend report for the following tickers: [TICKERS, e.g., AAPL, BTC-USD].
> 1. Use `yfinance` to fetch the last 30 days of closing prices and volume.
> 2. Use Pandas to calculate the 7-day Moving Average and RSI (Relative Strength Index).
> 3. Generate a Markdown report highlighting potential 'Buy' or 'Overbought' signals based on the RSI.
> 4. Include a simple Plotly chart saved as an HTML file `market_trends.html`."

---

## 📧 Template 4: The Content Factory (Marketer)
**Goal:** Create a high-converting cold email campaign.

**Prompt:**
> "Write a sequence of 5 Cold Emails to pitch the [LEAD LIST CSV] we scraped. The product is a [PRODUCT DESCRIPTION]. Use the AIDA framework. Output as email_campaign.md."

---

## 📊 Template 5: The Insight Report (Analyst)
**Goal:** Transform raw lead data into actionable analytics.

**Prompt:**
> "Analyze leads.csv. 
> 1. Calculate the distribution of industries. 
> 2. Generate a Bar Chart of the top locations. 
> 3. Save the report as a Streamlit app dashboard_analytics.py."

---

## 🕵️ Template 6: The Niche Hunter (Researcher)
**Goal:** Identify high-potential market gaps and SaaS ideas.

**Prompt:**
> "Research the 'AI Legal Tools' market. 
> 1. Identify the top 3 competitors. 
> 2. Find 5 negative reviews for each to find gaps. 
> 3. Propose 3 'Micro-SaaS' ideas that solve these specific complaints."

---

## 🚀 Execution Instructions
1. Select the **Growth Engineer** role.
2. Paste your chosen template.
3. Replace placeholders (like `[TARGET URL]`) with your actual data source.
4. Run the task.