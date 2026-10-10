// Take a 1280x1024 viewport screenshot of books.toscrape.com with Chrome for Testing and record
// ground truth for the vision tasks: star ratings of the first row of books (not exposed in the
// accessibility tree, only as a CSS class + drawn stars) and the bounding box of the
// "Add to basket" button for "Sharp Objects".
// Usage: OUT_DIR=<dir> node screenshot.mjs (resolve playwright-core from <scratch>/npm/node_modules)
import { chromium } from "playwright-core";
import fs from "node:fs";

const out = process.env.OUT_DIR;
const browser = await chromium.launch({
  executablePath:
    process.env.CHROME_BIN,
  headless: true,
});
const page = await browser.newPage({ viewport: { width: 1280, height: 1024 }, deviceScaleFactor: 1 });
await page.goto("https://books.toscrape.com/", { waitUntil: "load" });
await page.screenshot({ path: `${out}/books_viewport.png` });
const truth = await page.evaluate(() => {
  const pods = [...document.querySelectorAll("article.product_pod")].slice(0, 4);
  const books = pods.map((p) => ({
    title: p.querySelector("h3 a").getAttribute("title"),
    rating: p.querySelector("p.star-rating").className.replace("star-rating", "").trim(),
  }));
  const sharp = pods.find((p) => p.querySelector("h3 a").getAttribute("title") === "Sharp Objects");
  const r = sharp.querySelector("button").getBoundingClientRect();
  return { books, sharp_add_to_basket_bbox: { x: r.x, y: r.y, w: r.width, h: r.height } };
});
fs.writeFileSync(`${out}/vision_truth.json`, JSON.stringify(truth, null, 1));
console.log(JSON.stringify(truth));
await browser.close();
