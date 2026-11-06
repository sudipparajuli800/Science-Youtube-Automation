import {ensureBrowser, openBrowser} from '@remotion/renderer';
import {writeFile, rm} from 'node:fs/promises';
const flag = new URL('./.renderer-ready', import.meta.url);
await rm(flag, {force: true});
await ensureBrowser({chromeMode: 'headless-shell'});
const browser = await openBrowser('chrome', {chromeMode: 'headless-shell'});
await browser.close({silent: true});
await writeFile(flag, 'ready');
console.log('Remotion browser launch verified.');
