import React, { useEffect, useRef } from 'react';
import { createChart, ColorType } from 'lightweight-charts';

interface CandleChartProps {
    data: any[];
}

const CandleChart: React.FC<CandleChartProps> = ({ data }) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const seriesRef = useRef<any>(null);
    const chartRef = useRef<any>(null);
    const firstDataRef = useRef(true);

    // 차트 생성 — 마운트 시 1회 (종목/모드 변경은 key prop으로 처리)
    useEffect(() => {
        if (!containerRef.current) return;

        const chart = createChart(containerRef.current, {
            layout: {
                background: { type: ColorType.Solid, color: '#1e293b' },
                textColor: '#d1d5db',
            },
            grid: {
                vertLines: { color: '#334155' },
                horzLines: { color: '#334155' },
            },
            width: containerRef.current.clientWidth,
            height: containerRef.current.clientHeight || 500,
            timeScale: {
                rightOffset: 5,
                barSpacing: 8,
            },
        });

        const series = chart.addCandlestickSeries({
            upColor: '#22c55e',
            downColor: '#ef4444',
            borderVisible: false,
            wickUpColor: '#22c55e',
            wickDownColor: '#ef4444',
        });

        chartRef.current = chart;
        seriesRef.current = series;
        firstDataRef.current = true;

        const handleResize = () => {
            if (containerRef.current) {
                chart.applyOptions({
                    width: containerRef.current.clientWidth,
                    height: containerRef.current.clientHeight || 500,
                });
            }
        };

        const ro = new ResizeObserver(handleResize);
        ro.observe(containerRef.current);

        return () => {
            ro.disconnect();
            chart.remove();
            chartRef.current = null;
            seriesRef.current = null;
        };
    }, []);

    // 데이터 갱신 — 차트 재생성 없이 series만 업데이트
    useEffect(() => {
        if (!seriesRef.current || data.length === 0) return;

        seriesRef.current.setData(data);

        // 최초 데이터 로드 시에만 전체 맞춤 (이후 폴링 갱신은 뷰포트 유지)
        if (firstDataRef.current && chartRef.current) {
            chartRef.current.timeScale().fitContent();
            firstDataRef.current = false;
        }
    }, [data]);

    return (
        <div
            ref={containerRef}
            className="w-full h-full rounded-lg overflow-hidden border border-slate-700"
        />
    );
};

export default CandleChart;
