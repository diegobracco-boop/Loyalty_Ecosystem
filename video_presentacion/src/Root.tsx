import React from "react";
import { Composition } from "remotion";
import { FPS, H, W } from "./theme";
import { LoyaltyVideo, TOTAL_FRAMES } from "./Video";

export const RemotionRoot: React.FC = () => (
  <Composition id="LoyaltyEcosystem" component={LoyaltyVideo} durationInFrames={TOTAL_FRAMES} fps={FPS} width={W} height={H} />
);
