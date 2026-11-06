import React from 'react';
import {Composition, registerRoot} from 'remotion';
import {Scene} from './Scene';

const Root = () => <Composition id="ScienceScene" component={Scene}
  width={1080} height={1920} fps={30} durationInFrames={180}
  defaultProps={{spec: {template: 'flow', title: 'A process', nodes: [
    {label: 'Source', icon: 'particle'}, {label: 'Destination', icon: 'leaf'}]},
    frames: 180, width: 1080, height: 1920}}
  calculateMetadata={({props}) => ({durationInFrames: props.frames,
    width: props.width, height: props.height, fps: 30})}/>;
registerRoot(Root);
