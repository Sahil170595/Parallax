# Workflow Report

Total steps: 10

## Step 00 — Home page | Form valid
- URL: `https://www.wikipedia.org/`
- Action: `navigate(https://wikipedia.com)`
![Step 00](00_full.png)

## Step 01 — Home page | Form valid
- URL: `https://www.wikipedia.org/`
- Action: `wait`
![Step 01](01_full.png)

## Step 02 — Home page | Form valid
- URL: `https://www.wikipedia.org/`
- Action: `focus`
![Step 02](02_full.png)

## Step 03 — Home page | Form valid
- URL: `https://www.wikipedia.org/`
- Action: `type(input[name='search'])`
![Step 03](03_full.png)

## Step 04 — Wiki/special:search page | Dialog open | Form valid | Structure changed (1.00)
- URL: `https://en.wikipedia.org/wiki/Special:Search?go=Go&search=Cake+recipe&ns0=1`
- Action: `key_press`
- **Modal/Dialog present**
![Step 04](04_full.png)

## Step 05 — Wiki/special:search page | Dialog open | Form valid
- URL: `https://en.wikipedia.org/wiki/Special:Search?go=Go&search=Cake+recipe&ns0=1`
- Action: `wait`
- **Modal/Dialog present**
![Step 05](05_full.png)

## Step 06 — Wiki/cake page | Form valid | Structure changed (0.93)
- URL: `https://en.wikipedia.org/wiki/Cake`
- Action: `click(link:Cake)`
![Step 06](06_full.png)

## Step 07 — Wiki/cake page | Form valid
- URL: `https://en.wikipedia.org/wiki/Cake`
- Action: `wait`
![Step 07](07_full.png)

## Step 08 — Wiki/cake page | Form valid
- URL: `https://en.wikipedia.org/wiki/Cake`
- Action: `scroll`
![Step 08](08_full.png)

## Step 09 — Wiki/cake page | Form valid
- URL: `https://en.wikipedia.org/wiki/Cake`
- Action: `wait`
![Step 09](09_full.png)
