import Svg, {
  Circle,
  Defs,
  LinearGradient,
  Path,
  Rect,
  Stop,
} from "react-native-svg";

import { colors } from "../theme";

interface AppLogoProps {
  size?: number;
  showBackground?: boolean;
}

export function AppLogo({ size = 44, showBackground = true }: AppLogoProps) {
  return (
    <Svg height={size} viewBox="0 0 1024 1024" width={size}>
      <Defs>
        <LinearGradient id="logoRing" x1="208" x2="836" y1="178" y2="846">
          <Stop offset="0" stopColor={colors.primary} />
          <Stop offset="0.54" stopColor={colors.info} />
          <Stop offset="1" stopColor={colors.accent} />
        </LinearGradient>
        <LinearGradient id="logoCurve" x1="267" x2="757" y1="590" y2="386">
          <Stop offset="0" stopColor={colors.accent} />
          <Stop offset="0.5" stopColor={colors.primary} />
          <Stop offset="1" stopColor={colors.info} />
        </LinearGradient>
      </Defs>
      {showBackground ? (
        <Rect fill={colors.backgroundRaised} height="1024" rx="232" width="1024" />
      ) : null}
      <Path
        d="M176 512c76-139 193-208 336-208s260 69 336 208c-76 139-193 208-336 208S252 651 176 512Z"
        fill={colors.surface}
        stroke="url(#logoRing)"
        strokeWidth="44"
      />
      <Circle
        cx="512"
        cy="512"
        fill={colors.background}
        r="118"
        stroke={colors.text}
        strokeOpacity="0.9"
        strokeWidth="34"
      />
      <Circle cx="512" cy="512" fill={colors.primary} r="54" />
      <Path
        d="M274 596c80 0 90-126 176-126 73 0 82 84 150 84 55 0 83-54 150-90"
        fill="none"
        stroke="url(#logoCurve)"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="46"
      />
      <Path
        d="M512 204v92M512 728v92M204 512h92M728 512h92"
        stroke={colors.accent}
        strokeLinecap="round"
        strokeWidth="34"
      />
    </Svg>
  );
}
