import test from 'node:test';
import assert from 'node:assert/strict';
import {beatState} from '../src/storytelling.mjs';

test('source cues reveal one subject at a time, then hold the finished diagram', () => {
  assert.equal(beatState(20, 1, [0, 35, 60], 100, 3).visible, 0);
  assert.equal(beatState(51, 1, [0, 35, 60], 100, 3).visible, 1);
  assert.equal(beatState(99, 1, [0, 35, 60], 100, 3).visible, 1);
});

test('focus keeps earlier subjects visible while emphasizing the spoken one', () => {
  assert.equal(beatState(50, 0, [0, 35], 100, 2, 'focus').opacity, .65);
  assert.equal(beatState(50, 1, [0, 35], 100, 2, 'focus').opacity, 1);
  assert.equal(beatState(20, 1, [0, 35], 100, 2, 'focus').opacity, 0);
});

test('assembly finishes without ongoing drift or rotation', () => {
  const settled = beatState(90, 1, [0, 35], 100, 2, 'assemble');
  assert.equal(settled.shift, 0);
  assert.equal(settled.rotation, 0);
});

test('seeking backward produces exactly the original frame state', () => {
  const first = beatState(40, 1, [0, 35], 100, 2, 'assemble');
  beatState(99, 1, [0, 35], 100, 2, 'assemble');
  assert.deepEqual(beatState(40, 1, [0, 35], 100, 2, 'assemble'), first);
});

test('missing word cues still have a bounded stagger and a final reading hold', () => {
  assert.equal(beatState(0, 2, [], 100, 3).visible, 0);
  assert.equal(beatState(80, 2, [], 100, 3).visible, 1);
  assert.equal(beatState(80, 0, [], 100, 3, 'focus').opacity, .65);
});

test('a label spoken near the end does not leave an unfinished drawing', () => {
  assert.equal(beatState(99, 1, [0, 94], 100, 2).visible, 1);
  assert.equal(beatState(99, 1, [0, 99], 100, 2).visible, 1);
});
