import { describe, expect, it } from 'vitest';

import { analyzeGraph, shortestPath } from './graph-metrics';

const nodes = (...ids: string[]) => ids.map((id) => ({ id }));

describe('graph metrics', () => {
	it('finds the bridge, components, and degree roles', () => {
		// A-B-C  and  C-D-E : C is the bridge between the two triang's chains.
		// F is isolated. G->H is a separate component (source/sink).
		const g = analyzeGraph(
			nodes('A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'),
			[
				{ source: 'A', target: 'B' },
				{ source: 'B', target: 'C' },
				{ source: 'C', target: 'D' },
				{ source: 'D', target: 'E' },
				{ source: 'G', target: 'H' }
			]
		);

		// C sits on every A/B ↔ D/E path → highest betweenness.
		expect(g.bridge).toBe('C');
		// F has no links; G/H form a separate component.
		expect(g.isolated).toEqual(['F']);
		// A-E chain, G-H, and F(alone) → 3 connected components.
		expect(g.components).toBe(3);
		// G points at H with nothing pointing back → source; H → sink.
		expect(g.sources).toContain('G');
		expect(g.sinks).toContain('H');
		// A has one incoming? No — A only has outgoing, so it's an orphan (no in).
		expect(g.orphans).toContain('A');
		// Degree metrics present for every node, pagerank sums to ~1.
		const total = [...g.metrics.values()].reduce((s, m) => s + m.pagerank, 0);
		expect(total).toBeCloseTo(1, 5);
	});

	it('detects communities on two clear clusters', () => {
		// Triangle {A,B,C} and triangle {X,Y,Z}, joined by a single edge C-X.
		const g = analyzeGraph(nodes('A', 'B', 'C', 'X', 'Y', 'Z'), [
			{ source: 'A', target: 'B' },
			{ source: 'B', target: 'C' },
			{ source: 'C', target: 'A' },
			{ source: 'X', target: 'Y' },
			{ source: 'Y', target: 'Z' },
			{ source: 'Z', target: 'X' },
			{ source: 'C', target: 'X' }
		]);
		expect(g.communities).toBeGreaterThanOrEqual(2);
	});

	it('computes shortest paths and returns null when unreachable', () => {
		const ns = nodes('A', 'B', 'C', 'D', 'Z');
		const es = [
			{ source: 'A', target: 'B' },
			{ source: 'B', target: 'C' },
			{ source: 'C', target: 'D' }
		];
		expect(shortestPath(ns, es, 'A', 'D')).toEqual(['A', 'B', 'C', 'D']);
		expect(shortestPath(ns, es, 'A', 'Z')).toBeNull(); // Z is disconnected
	});
});
