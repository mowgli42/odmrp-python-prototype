#!/usr/bin/env node
/**
 * Capture README + walkthrough screenshots for dynamic-mesh (default) UI.
 */
import { chromium } from 'playwright'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.resolve(__dirname, '../..')
const OUT = path.join(ROOT, 'docs/walkthrough')
const URL = process.env.ODMRP_UI_URL || 'http://127.0.0.1:5173/'

async function clickNode(page, id) {
  await page.evaluate((nid) => {
    const labels = [...document.querySelectorAll('svg.net text.label')]
    const t = labels.find((el) => el.textContent?.trim() === String(nid))
    const shape = t?.previousElementSibling
    shape?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
  }, id)
  await page.waitForTimeout(450)
}

async function waitForTrace(page) {
  await page.waitForSelector('section.trace ol li', { timeout: 25000 })
  await page.waitForTimeout(500)
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
  await page.goto(URL, { waitUntil: 'networkidle', timeout: 45000 })
  await page.waitForSelector('text=ODMRP', { timeout: 20000 })
  // Ensure dynamic-mesh is selected (UI default)
  const scenario = page.locator('select[aria-label="Scenario"]')
  if (await scenario.count()) {
    await scenario.selectOption('dynamic-mesh')
    await page.waitForTimeout(1500)
  }
  await waitForTrace(page)

  const allChip = page.getByRole('tab', { name: 'all' })
  if (await allChip.count()) await allChip.click()

  // Hero / overview — full page with 16-node grid + Trace
  await page.screenshot({
    path: path.join(OUT, 'readme_hero.png'),
    fullPage: true,
  })
  await page.screenshot({
    path: path.join(OUT, 'walkthrough_01_loaded_basic_mesh.png'),
    fullPage: true,
  })

  // Native node 5 — inspector with log tail
  await clickNode(page, 5)
  await page.waitForSelector('pre.log', { timeout: 8000 }).catch(() => null)
  await page.waitForTimeout(600)
  await page.screenshot({
    path: path.join(OUT, 'walkthrough_02_inspector_node1.png'),
    fullPage: true,
  })
  // Dedicated native-log crop
  const insp = page.locator('aside.insp')
  if (await insp.count()) {
    await insp.screenshot({ path: path.join(OUT, 'walkthrough_02b_native_log.png') })
  }

  // Send a message
  const textInput = page.locator('section.msg input').last()
  if (await textInput.count()) {
    await textInput.fill('Walkthrough ping')
    await page.getByRole('button', { name: /^Send$/i }).click()
    await page.waitForTimeout(1400)
  }
  await page.screenshot({
    path: path.join(OUT, 'walkthrough_03_after_send.png'),
    fullPage: true,
  })

  // Receiver inbox (member node 15)
  await clickNode(page, 15)
  await page.waitForTimeout(400)
  await page.screenshot({
    path: path.join(OUT, 'walkthrough_04_receiver_inbox.png'),
    fullPage: true,
  })

  // Trace-focused: deliver filter
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

  // Also capture classic basic-mesh for the docs
  if (await scenario.count()) {
    await scenario.selectOption('basic-mesh')
    await page.waitForTimeout(1500)
    await waitForTrace(page)
    await page.screenshot({
      path: path.join(OUT, 'walkthrough_06_basic_mesh.png'),
      fullPage: true,
    })
  }

  console.log('Wrote screenshots to', OUT)
  await browser.close()
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
