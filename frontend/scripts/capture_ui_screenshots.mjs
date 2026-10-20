#!/usr/bin/env node
/**
 * Capture README + walkthrough screenshots with Trace panel populated.
 */
import { chromium } from 'playwright'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.resolve(__dirname, '../..')
const OUT = path.join(ROOT, 'docs/walkthrough')
const URL = process.env.ODMRP_UI_URL || 'http://127.0.0.1:5173/'

async function waitForTrace(page) {
  await page.waitForSelector('section.trace ol li', { timeout: 20000 })
  await page.waitForTimeout(400)
}

async function main() {
  const browser = await chromium.launch({
    executablePath: process.env.CHROMIUM_PATH || '/usr/bin/chromium',
    headless: true,
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  })
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1100 },
    deviceScaleFactor: 1,
  })
  await page.goto(URL, { waitUntil: 'networkidle', timeout: 30000 })
  await page.waitForSelector('text=ODMRP', { timeout: 15000 })
  await waitForTrace(page)

  const allChip = page.getByRole('tab', { name: 'all' })
  if (await allChip.count()) await allChip.click()

  // Hero / overview: full page including Trace with live events
  await page.screenshot({
    path: path.join(OUT, 'readme_hero.png'),
    fullPage: true,
  })
  await page.screenshot({
    path: path.join(OUT, 'walkthrough_01_loaded_basic_mesh.png'),
    fullPage: true,
  })

  // Select node 1 for inspector
  await page.evaluate(() => {
    const labels = [...document.querySelectorAll('svg.net text.label')]
    const t = labels.find((el) => el.textContent?.trim() === '1')
    const shape = t?.previousElementSibling
    shape?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
  })
  await page.waitForTimeout(400)
  await page.screenshot({
    path: path.join(OUT, 'walkthrough_02_inspector_node1.png'),
    fullPage: true,
  })

  // Send a message so Trace + delivery update
  const textInput = page.locator('section.msg input').last()
  if (await textInput.count()) {
    await textInput.fill('Walkthrough ping')
    await page.getByRole('button', { name: /^Send$/i }).click()
    await page.waitForTimeout(1200)
  }
  await page.screenshot({
    path: path.join(OUT, 'walkthrough_03_after_send.png'),
    fullPage: true,
  })

  // Receiver inbox (node 5)
  await page.evaluate(() => {
    const labels = [...document.querySelectorAll('svg.net text.label')]
    const t = labels.find((el) => el.textContent?.trim() === '5')
    const shape = t?.previousElementSibling
    shape?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
  })
  await page.waitForTimeout(400)
  await page.screenshot({
    path: path.join(OUT, 'walkthrough_04_receiver_inbox.png'),
    fullPage: true,
  })

  // Trace-focused: filter to deliver and capture
  const deliver = page.getByRole('tab', { name: 'deliver' })
  if (await deliver.count()) await deliver.click()
  await page.waitForTimeout(200)
  await page.locator('section.trace').scrollIntoViewIfNeeded()
  await page.waitForTimeout(200)
  await page.screenshot({
    path: path.join(OUT, 'walkthrough_05_trace_panel.png'),
    fullPage: true,
  })

  const trace = page.locator('section.trace')
  if (await trace.count()) {
    await trace.screenshot({ path: path.join(OUT, 'walkthrough_05b_trace_closeup.png') })
  }

  const bottom = page.locator('div.bottom')
  if (await bottom.count()) {
    await bottom.screenshot({ path: path.join(OUT, 'walkthrough_05c_messaging_and_trace.png') })
  }

  console.log('Wrote screenshots to', OUT)
  await browser.close()
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
