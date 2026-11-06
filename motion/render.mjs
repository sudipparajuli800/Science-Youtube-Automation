import {bundle} from '@remotion/bundler';
import {renderMedia, selectComposition} from '@remotion/renderer';
import {readFile, writeFile, mkdir} from 'node:fs/promises';
import {existsSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import crypto from 'node:crypto';

const [propsFile, output] = process.argv.slice(2);
if (!propsFile || !output) throw new Error('Usage: node render.mjs props.json output.mp4');
const root = path.dirname(fileURLToPath(import.meta.url));
const props = JSON.parse(await readFile(propsFile, 'utf8'));
props.font = (await readFile(path.join(root, '../automation/fonts/Barlow-Regular.ttf'))).toString('base64');
props.boldFont = (await readFile(path.join(root, '../automation/fonts/Barlow-Bold.ttf'))).toString('base64');
const version = crypto.createHash('sha256');
for (const name of ['src/index.jsx', 'src/Scene.jsx', 'package-lock.json']) {
  version.update(await readFile(path.join(root, name)));
}
const stamp = version.digest('hex');
const bundleDir = path.join(root, '.bundle');
const stampPath = path.join(root, '.bundle-stamp');
if (!existsSync(path.join(bundleDir, 'index.html')) || !existsSync(stampPath) ||
    (await readFile(stampPath, 'utf8')) !== stamp) {
  await bundle({entryPoint: path.join(root, 'src/index.jsx'), outDir: bundleDir});
  await writeFile(stampPath, stamp);
}
const options = {serveUrl: bundleDir, inputProps: props, chromeMode: 'headless-shell'};
const composition = await selectComposition({...options, id: 'ScienceScene'});
await mkdir(path.dirname(path.resolve(output)), {recursive: true});
await renderMedia({...options, composition, outputLocation: output, codec: 'h264',
  pixelFormat: 'yuv420p', crf: 18, concurrency: 1});
console.log(`Rendered ${props.spec.template}: ${output}`);
