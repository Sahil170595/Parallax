# Workflow Report

Total steps: 6

## Step 00 — Form valid
- URL: `https://www.wikipedia.org/`
- Action: `navigate(https://wikipedia.org)`
![Step 00](00_full.png)

## Step 01 — Form valid
- URL: `https://www.wikipedia.org/`
- Action: `wait`
![Step 01](01_full.png)

## Step 02 — Form valid
- URL: `https://www.wikipedia.org/`
- Action: `type(input[name='search'])`
![Step 02](02_full.png)

## Step 03 — Form valid
- URL: `https://www.wikipedia.org/`
- Action: `submit(form#searchform button[type='submit']) [FAILED]`
![Step 03](03_full.png)

## Step 04 — Form valid
- URL: `https://www.wikipedia.org/`
- Action: `wait`
![Step 04](04_full.png)

## Step 05 — Form valid
- URL: `https://en.wikipedia.org/wiki/Chocolate_cake`
- Action: `click(link:Chocolate cake)`
![Step 05](05_full.png)
