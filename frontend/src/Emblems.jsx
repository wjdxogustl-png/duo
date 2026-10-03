import { DOKDO, GYEONGNAM_PATH, KOREA_PATH, MAP_VIEWBOX } from "./assets/koreaMap.js";

// 태극기: 국기법 시행령 비율(가로:세로 3:2, 태극 지름 = 세로의 1/2)을 따른다.
// 깃면 72×48, 태극 반지름 12 기준. 괘는 대각선 위, 태극에서 지름의 1/4 떨어진 곳에 둔다.
const DIAG = (Math.atan2(48, 72) * 180) / Math.PI; // 왼쪽 위 → 오른쪽 아래 대각선 각도

// 효(爻) 3개: true = 이어진 막대, false = 가운데가 끊어진 막대
const TRIGRAMS = [
  { name: "건", angle: 180 + DIAG, lines: [true, true, true] },   // 왼쪽 위
  { name: "곤", angle: DIAG, lines: [false, false, false] },      // 오른쪽 아래
  { name: "감", angle: -DIAG, lines: [false, true, false] },      // 오른쪽 위
  { name: "리", angle: 180 - DIAG, lines: [true, false, true] },  // 왼쪽 아래
];

function Trigram({ angle, lines }) {
  // 지름 24 기준: 괘 길이 12, 효 두께 2, 효 사이 1, 끊어진 틈 1, 태극과의 거리 6
  return (
    <g transform={`rotate(${angle}) translate(22 0)`}>
      {lines.map((solid, i) => {
        const x = -4 + i * 3;
        return solid ? (
          <rect key={i} x={x} y={-6} width={2} height={12} />
        ) : (
          <g key={i}>
            <rect x={x} y={-6} width={2} height={5.5} />
            <rect x={x} y={0.5} width={2} height={5.5} />
          </g>
        );
      })}
    </g>
  );
}

export function Taegukgi({ className, title = "태극기" }) {
  return (
    <svg className={className} viewBox="-36 -24 72 48" role="img" aria-label={title}>
      <title>{title}</title>
      <rect x={-36} y={-24} width={72} height={48} fill="#fff" />
      <g transform={`rotate(${DIAG})`}>
        <circle r={12} fill="#0047A0" />
        <path d="M-12 0A12 12 0 0 1 12 0A6 6 0 0 0 0 0A6 6 0 0 1 -12 0Z" fill="#CD2E3A" />
      </g>
      <g fill="#000">
        {TRIGRAMS.map((t) => <Trigram key={t.name} {...t} />)}
      </g>
    </svg>
  );
}

export function KoreaMap({ className, title }) {
  return (
    <svg className={className} viewBox={MAP_VIEWBOX} role="img" aria-label={title}>
      <title>{title}</title>
      <path className="land" d={KOREA_PATH} />
      <path className="highlight" d={GYEONGNAM_PATH} />
      <circle className="land dot" cx={DOKDO[0]} cy={DOKDO[1]} r={1.4} />
    </svg>
  );
}
