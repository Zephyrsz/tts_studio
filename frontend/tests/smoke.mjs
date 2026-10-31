import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const source=await readFile(new URL('../src/api.js', import.meta.url),'utf8');
assert.match(source,/api\/v1\/batches/); assert.match(source,/audioURL/);
console.log('frontend module smoke: PASS');
