import React, { useEffect, useRef } from 'react';
import { createChart, ColorType, type IChartApi, type ISeriesApi } from 'lightweight-charts';

interface CandleData {
    time: string | number;
    open: number;
    high: number;
    low: number;
    close: number;
    volume?: number;
}

interface EnrichedBar extends CandleData {
    ma20: number | null;
    ma60: number | null;
}

interface CandleChartProps {
    data: CandleData[];
}

// MA 계산 헬퍼
function calcMA(closes: number[], period: number): (number | null)[] {
    return closes.map((_, i) =>
        i < period - 1 ? null : closes.slice(i - period + 1, i + 1).reduce((a, b) => a + b, 0) / period
    );
}

function fmtVol(v: number): string {
    if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(2)}M`;
    if (v >= 1_000)     return `${(v / 1_000).toFixed(1)}K`;
    return String(v);
}

function fmtPrice(v: number): string {
    return v.toLocaleString('ko-KR');
}

const CHART_BG   = '#1e293b';
const GRID_COLOR = '#334155';
const TEXT_COLOR = '#94a3b8';
const UP_COLOR   = '#22c55e';
const DOWN_COLOR = '#ef4444';
const MA20_COLOR = '#f59e0b';
const MA60_COLOR = '#60a5fa';

const CandleChart: React.FC<CandleChartProps> = ({ data }) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const tooltipRef   = useRef<HTMLDivElement>(null);
    const chartRef     = useRef<IChartApi | null>(null);
    const candleRef    = useRef<ISeriesApi<'Candlestick'> | null>(null);
    const volRef       = useRef<ISeriesApi<'Histogram'> | null>(null);
    const ma20Ref      = useRef<ISeriesApi<'Line'> | null>(null);
    const ma60Ref      = useRef<ISeriesApi<'Line'> | null>(null);
    const firstDataRef = useRef(true);
    // 최신 bar 맵: time → EnrichedBar (crosshair 핸들러에서 조회)
    const barMapRef    = useRef<Map<string | number, EnrichedBar>>(new Map());

    // 차트 생성 — 마운트 시 1회
    useEffect(() => {
        if (!containerRef.current || !tooltipRef.current) return;

        const totalH = containerRef.current.clientHeight || 500;

        const chart = createChart(containerRef.current, {
            layout: {
                background: { type: ColorType.Solid, color: CHART_BG },
                textColor: TEXT_COLOR,
            },
            grid: {
                vertLines: { color: GRID_COLOR },
                horzLines: { color: GRID_COLOR },
            },
            width:  containerRef.current.clientWidth,
            height: totalH,
            timeScale: {
                rightOffset: 5,
                barSpacing: 8,
                borderColor: GRID_COLOR,
            },
            rightPriceScale: { borderColor: GRID_COLOR },
            crosshair: { mode: 1 },
        });

        // ── 캔들스틱 ─────────────────────────────────────────
        const candleSeries = chart.addCandlestickSeries({
            upColor:       UP_COLOR,
            downColor:     DOWN_COLOR,
            borderVisible: false,
            wickUpColor:   UP_COLOR,
            wickDownColor: DOWN_COLOR,
            priceScaleId: 'right',
        });
        candleSeries.priceScale().applyOptions({ scaleMargins: { top: 0.05, bottom: 0.28 } });

        // ── MA20 ─────────────────────────────────────────────
        const ma20Series = chart.addLineSeries({
            color: MA20_COLOR, lineWidth: 1,
            priceScaleId: 'right',
            lastValueVisible: true, priceLineVisible: false,
            title: 'MA20', crosshairMarkerVisible: false,
        });

        // ── MA60 ─────────────────────────────────────────────
        const ma60Series = chart.addLineSeries({
            color: MA60_COLOR, lineWidth: 1,
            priceScaleId: 'right',
            lastValueVisible: true, priceLineVisible: false,
            title: 'MA60', crosshairMarkerVisible: false,
        });

        // ── 거래량 히스토그램 ─────────────────────────────────
        const volSeries = chart.addHistogramSeries({
            priceScaleId: 'volume',
            priceFormat: { type: 'volume' },
            lastValueVisible: false, priceLineVisible: false,
        });
        volSeries.priceScale().applyOptions({ scaleMargins: { top: 0.80, bottom: 0.00 } });

        chartRef.current  = chart;
        candleRef.current = candleSeries;
        ma20Ref.current   = ma20Series;
        ma60Ref.current   = ma60Series;
        volRef.current    = volSeries;
        firstDataRef.current = true;

        // ── 크로스헤어 툴팁 ──────────────────────────────────
        const tooltip = tooltipRef.current!;

        chart.subscribeCrosshairMove(param => {
            if (!containerRef.current) return;
            const cw = containerRef.current.clientWidth;
            const ch = containerRef.current.clientHeight;

            // 차트 영역 벗어나거나 시간 정보 없으면 숨김
            if (
                !param.point ||
                !param.time ||
                param.point.x < 0 || param.point.x > cw ||
                param.point.y < 0 || param.point.y > ch
            ) {
                tooltip.style.display = 'none';
                return;
            }

            const bar = barMapRef.current.get(param.time as string | number);
            if (!bar) { tooltip.style.display = 'none'; return; }

            const isUp = bar.close >= bar.open;
            const priceColor = isUp ? UP_COLOR : DOWN_COLOR;
            const changePct  = ((bar.close - bar.open) / bar.open * 100).toFixed(2);
            const changeSign = isUp ? '+' : '';

            // 날짜/시간 포맷
            let timeStr = '';
            if (typeof param.time === 'number') {
                timeStr = new Date(param.time * 1000)
                    .toLocaleString('ko-KR', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
            } else {
                timeStr = String(param.time);
            }

            tooltip.innerHTML = `
                <div style="color:${TEXT_COLOR};font-size:10px;margin-bottom:4px;">${timeStr}</div>
                <div style="display:grid;grid-template-columns:auto auto;gap:1px 8px;font-size:11px;">
                    <span style="color:${TEXT_COLOR}">시가</span><span style="color:${priceColor};font-family:monospace">${fmtPrice(bar.open)}</span>
                    <span style="color:${TEXT_COLOR}">고가</span><span style="color:${UP_COLOR};font-family:monospace">${fmtPrice(bar.high)}</span>
                    <span style="color:${TEXT_COLOR}">저가</span><span style="color:${DOWN_COLOR};font-family:monospace">${fmtPrice(bar.low)}</span>
                    <span style="color:${TEXT_COLOR}">종가</span><span style="color:${priceColor};font-family:monospace;font-weight:700">${fmtPrice(bar.close)} <span style="font-size:10px">(${changeSign}${changePct}%)</span></span>
                    ${bar.volume ? `<span style="color:${TEXT_COLOR}">거래량</span><span style="color:#e2e8f0;font-family:monospace">${fmtVol(bar.volume)}</span>` : ''}
                    ${bar.ma20 != null ? `<span style="color:${MA20_COLOR}">MA20</span><span style="color:${MA20_COLOR};font-family:monospace">${fmtPrice(Math.round(bar.ma20))}</span>` : ''}
                    ${bar.ma60 != null ? `<span style="color:${MA60_COLOR}">MA60</span><span style="color:${MA60_COLOR};font-family:monospace">${fmtPrice(Math.round(bar.ma60))}</span>` : ''}
                </div>
            `;

            // 툴팁 위치: 오른쪽 공간 충분하면 오른쪽, 아니면 왼쪽
            tooltip.style.display = 'block';
            const tw = tooltip.offsetWidth  || 160;
            const th = tooltip.offsetHeight || 120;
            const MARGIN = 12;
            const x = param.point.x + MARGIN + tw > cw
                ? param.point.x - tw - MARGIN
                : param.point.x + MARGIN;
            const y = Math.max(4, Math.min(param.point.y - th / 2, ch - th - 4));
            tooltip.style.left = `${x}px`;
            tooltip.style.top  = `${y}px`;
        });

        // 리사이즈
        const handleResize = () => {
            if (!containerRef.current) return;
            chart.applyOptions({
                width:  containerRef.current.clientWidth,
                height: containerRef.current.clientHeight || 500,
            });
        };
        const ro = new ResizeObserver(handleResize);
        ro.observe(containerRef.current);

        return () => {
            ro.disconnect();
            chart.remove();
            chartRef.current = candleRef.current = ma20Ref.current = ma60Ref.current = volRef.current = null;
        };
    }, []);

    // 데이터 갱신
    useEffect(() => {
        if (!candleRef.current || !volRef.current || !ma20Ref.current || !ma60Ref.current) return;
        if (data.length === 0) return;

        // MA 계산
        const closes = data.map(c => c.close);
        const ma20   = calcMA(closes, 20);
        const ma60   = calcMA(closes, 60);

        // barMap 갱신 (크로스헤어 핸들러용)
        const newMap = new Map<string | number, EnrichedBar>();
        data.forEach((c, i) => {
            newMap.set(c.time, { ...c, ma20: ma20[i], ma60: ma60[i] });
        });
        barMapRef.current = newMap;

        // 캔들
        candleRef.current.setData(data as any);

        // 거래량
        volRef.current.setData(data.map(c => ({
            time:  c.time,
            value: c.volume ?? 0,
            color: c.close >= c.open ? `${UP_COLOR}99` : `${DOWN_COLOR}99`,
        })) as any);

        // MA20 / MA60
        ma20Ref.current.setData(
            data.map((c, i) => ({ time: c.time, value: ma20[i] }))
                .filter(d => d.value != null) as any
        );
        ma60Ref.current.setData(
            data.map((c, i) => ({ time: c.time, value: ma60[i] }))
                .filter(d => d.value != null) as any
        );

        // 최초 로드 시에만 전체 맞춤
        if (firstDataRef.current && chartRef.current) {
            chartRef.current.timeScale().fitContent();
            firstDataRef.current = false;
        }
    }, [data]);

    return (
        <div className="relative w-full h-full">
            <div
                ref={containerRef}
                className="w-full h-full rounded-lg overflow-hidden border border-slate-700"
            />
            {/* 크로스헤어 툴팁 */}
            <div
                ref={tooltipRef}
                style={{
                    display: 'none',
                    position: 'absolute',
                    pointerEvents: 'none',
                    zIndex: 10,
                    background: 'rgba(15,23,42,0.92)',
                    border: '1px solid #334155',
                    borderRadius: '6px',
                    padding: '7px 10px',
                    boxShadow: '0 4px 12px rgba(0,0,0,0.5)',
                    minWidth: '148px',
                    backdropFilter: 'blur(4px)',
                }}
            />
        </div>
    );
};

export default CandleChart;
