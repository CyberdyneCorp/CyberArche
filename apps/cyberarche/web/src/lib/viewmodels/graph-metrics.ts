/** Client-side graph analytics for the graph explorer (graph-explorer phase 2A).
 *
 * Pure functions over the returned nodes + directed edges: degree, PageRank,
 * betweenness (Brandes), closeness, connected components, communities (label
 * propagation), and shortest path. Small graphs (a teamspace/folder), so the
 * O(V·E) algorithms are fine. Kept dependency-free and unit-testable. */

export interface GNode {
	id: string;
}
export interface GEdge {
	source: string;
	target: string;
}

export interface NodeMetrics {
	inDeg: number;
	outDeg: number;
	degree: number;
	pagerank: number; // 0..1, sums to 1 across nodes
	betweenness: number; // normalized 0..1
	closeness: number; // 0..1
	community: number;
	component: number;
}

export interface GraphAnalysis {
	metrics: Map<string, NodeMetrics>;
	communities: number;
	components: number;
	isolated: string[]; // no links at all
	orphans: string[]; // no incoming references
	leaves: string[]; // exactly one connection
	sources: string[]; // outgoing but no incoming
	sinks: string[]; // incoming but no outgoing
	density: number; // 0..1
	avgDegree: number;
	mostConnected: string | null; // max degree
	bridge: string | null; // max betweenness
	bestStart: string | null; // max closeness
	authoritative: string | null; // max pagerank
}

function adjacency(nodeIds: string[], edges: GEdge[]) {
	const undirected = new Map<string, Set<string>>();
	const out = new Map<string, string[]>();
	const inDeg = new Map<string, number>();
	const outDeg = new Map<string, number>();
	for (const id of nodeIds) {
		undirected.set(id, new Set());
		out.set(id, []);
		inDeg.set(id, 0);
		outDeg.set(id, 0);
	}
	for (const e of edges) {
		if (!undirected.has(e.source) || !undirected.has(e.target)) continue;
		if (e.source === e.target) continue;
		undirected.get(e.source)!.add(e.target);
		undirected.get(e.target)!.add(e.source);
		out.get(e.source)!.push(e.target);
		outDeg.set(e.source, outDeg.get(e.source)! + 1);
		inDeg.set(e.target, inDeg.get(e.target)! + 1);
	}
	return { undirected, out, inDeg, outDeg };
}

function pagerank(nodeIds: string[], out: Map<string, string[]>): Map<string, number> {
	const n = nodeIds.length;
	const d = 0.85;
	let rank = new Map(nodeIds.map((id) => [id, 1 / n]));
	for (let iter = 0; iter < 40; iter++) {
		const next = new Map(nodeIds.map((id) => [id, (1 - d) / n]));
		let dangling = 0;
		for (const id of nodeIds) {
			const outs = out.get(id)!;
			if (outs.length === 0) {
				dangling += rank.get(id)!;
				continue;
			}
			const share = (d * rank.get(id)!) / outs.length;
			for (const t of outs) next.set(t, next.get(t)! + share);
		}
		if (dangling > 0) {
			const spread = (d * dangling) / n;
			for (const id of nodeIds) next.set(id, next.get(id)! + spread);
		}
		rank = next;
	}
	return rank;
}

/** Brandes' betweenness on the undirected graph, normalized to 0..1. */
function betweenness(
	nodeIds: string[],
	undirected: Map<string, Set<string>>
): Map<string, number> {
	const bc = new Map(nodeIds.map((id) => [id, 0]));
	for (const s of nodeIds) {
		const stack: string[] = [];
		const pred = new Map<string, string[]>(nodeIds.map((id) => [id, []]));
		const sigma = new Map(nodeIds.map((id) => [id, 0]));
		const dist = new Map(nodeIds.map((id) => [id, -1]));
		sigma.set(s, 1);
		dist.set(s, 0);
		const queue = [s];
		while (queue.length) {
			const v = queue.shift()!;
			stack.push(v);
			for (const w of undirected.get(v)!) {
				if (dist.get(w)! < 0) {
					dist.set(w, dist.get(v)! + 1);
					queue.push(w);
				}
				if (dist.get(w) === dist.get(v)! + 1) {
					sigma.set(w, sigma.get(w)! + sigma.get(v)!);
					pred.get(w)!.push(v);
				}
			}
		}
		const delta = new Map(nodeIds.map((id) => [id, 0]));
		while (stack.length) {
			const w = stack.pop()!;
			for (const v of pred.get(w)!) {
				delta.set(v, delta.get(v)! + (sigma.get(v)! / sigma.get(w)!) * (1 + delta.get(w)!));
			}
			if (w !== s) bc.set(w, bc.get(w)! + delta.get(w)!);
		}
	}
	// Undirected pairs counted twice; normalize by (n-1)(n-2).
	const n = nodeIds.length;
	const norm = n > 2 ? 2 / ((n - 1) * (n - 2)) : 0;
	for (const id of nodeIds) bc.set(id, bc.get(id)! * norm);
	return bc;
}

function closeness(
	nodeIds: string[],
	undirected: Map<string, Set<string>>
): Map<string, number> {
	const cc = new Map(nodeIds.map((id) => [id, 0]));
	const n = nodeIds.length;
	for (const s of nodeIds) {
		const dist = new Map<string, number>([[s, 0]]);
		const queue = [s];
		let sum = 0;
		let reached = 0;
		while (queue.length) {
			const v = queue.shift()!;
			for (const w of undirected.get(v)!) {
				if (!dist.has(w)) {
					dist.set(w, dist.get(v)! + 1);
					sum += dist.get(w)!;
					reached++;
					queue.push(w);
				}
			}
		}
		// Wasserman-Faust normalization for disconnected graphs.
		cc.set(s, sum > 0 ? (reached / (n - 1)) * (reached / sum) : 0);
	}
	return cc;
}

function components(
	nodeIds: string[],
	undirected: Map<string, Set<string>>
): Map<string, number> {
	const comp = new Map<string, number>();
	let c = 0;
	for (const id of nodeIds) {
		if (comp.has(id)) continue;
		const queue = [id];
		comp.set(id, c);
		while (queue.length) {
			const v = queue.shift()!;
			for (const w of undirected.get(v)!) {
				if (!comp.has(w)) {
					comp.set(w, c);
					queue.push(w);
				}
			}
		}
		c++;
	}
	return comp;
}

/** Communities by a single-level Louvain pass (local modularity optimization).
 * Reliable on small bridged graphs where label propagation collapses clusters. */
function communities(
	nodeIds: string[],
	undirected: Map<string, Set<string>>
): Map<string, number> {
	const deg = new Map(nodeIds.map((id) => [id, undirected.get(id)!.size]));
	const twoM = [...deg.values()].reduce((s, d) => s + d, 0) || 1;
	const comm = new Map(nodeIds.map((id, i) => [id, i]));
	const sigmaTot = new Map<number, number>();
	for (const id of nodeIds) {
		const c = comm.get(id)!;
		sigmaTot.set(c, (sigmaTot.get(c) ?? 0) + deg.get(id)!);
	}
	for (let pass = 0; pass < 20; pass++) {
		let improved = false;
		for (const id of nodeIds) {
			const ci = comm.get(id)!;
			const ki = deg.get(id)!;
			sigmaTot.set(ci, sigmaTot.get(ci)! - ki); // temporarily remove i
			const kiIn = new Map<number, number>();
			for (const nb of undirected.get(id)!) {
				const c = comm.get(nb)!;
				kiIn.set(c, (kiIn.get(c) ?? 0) + 1);
			}
			// Modularity gain of joining community c: kiIn(c) - Σtot(c)·ki/2m.
			let bestC = ci;
			let bestGain = (kiIn.get(ci) ?? 0) - (sigmaTot.get(ci) ?? 0) * (ki / twoM);
			for (const [c, kin] of [...kiIn].sort((a, b) => a[0] - b[0])) {
				const gain = kin - (sigmaTot.get(c) ?? 0) * (ki / twoM);
				if (gain > bestGain) {
					bestGain = gain;
					bestC = c;
				}
			}
			sigmaTot.set(bestC, (sigmaTot.get(bestC) ?? 0) + ki);
			comm.set(id, bestC);
			if (bestC !== ci) improved = true;
		}
		if (!improved) break;
	}
	// Re-index to 0..k-1 in first-seen order.
	const remap = new Map<number, number>();
	for (const id of nodeIds) {
		const l = comm.get(id)!;
		if (!remap.has(l)) remap.set(l, remap.size);
		comm.set(id, remap.get(l)!);
	}
	return comm;
}

function argmax(nodeIds: string[], value: (id: string) => number): string | null {
	let best: string | null = null;
	let bestV = -Infinity;
	for (const id of nodeIds) {
		const v = value(id);
		if (v > bestV) {
			bestV = v;
			best = id;
		}
	}
	return bestV > 0 ? best : null;
}

export function analyzeGraph(nodes: GNode[], edges: GEdge[]): GraphAnalysis {
	const ids = nodes.map((n) => n.id);
	const { undirected, out, inDeg, outDeg } = adjacency(ids, edges);
	const pr = pagerank(ids, out);
	const bc = betweenness(ids, undirected);
	const cc = closeness(ids, undirected);
	const comm = communities(ids, undirected);
	const comp = components(ids, undirected);

	const metrics = new Map<string, NodeMetrics>();
	for (const id of ids) {
		const degree = undirected.get(id)!.size;
		metrics.set(id, {
			inDeg: inDeg.get(id)!,
			outDeg: outDeg.get(id)!,
			degree,
			pagerank: pr.get(id)!,
			betweenness: bc.get(id)!,
			closeness: cc.get(id)!,
			community: comm.get(id)!,
			component: comp.get(id)!
		});
	}

	const isolated: string[] = [];
	const orphans: string[] = [];
	const leaves: string[] = [];
	const sources: string[] = [];
	const sinks: string[] = [];
	for (const id of ids) {
		const m = metrics.get(id)!;
		if (m.degree === 0) isolated.push(id);
		else if (m.degree === 1) leaves.push(id);
		if (m.inDeg === 0 && m.outDeg > 0) sources.push(id);
		if (m.outDeg === 0 && m.inDeg > 0) sinks.push(id);
		if (m.inDeg === 0 && m.degree > 0) orphans.push(id);
	}

	const n = ids.length;
	const undirectedEdgeCount = [...undirected.values()].reduce((s, set) => s + set.size, 0) / 2;
	const density = n > 1 ? (2 * undirectedEdgeCount) / (n * (n - 1)) : 0;
	const avgDegree = n > 0 ? (2 * undirectedEdgeCount) / n : 0;
	const communityCount = new Set([...comm.values()]).size;
	const componentCount = new Set([...comp.values()]).size;

	return {
		metrics,
		communities: communityCount,
		components: componentCount,
		isolated,
		orphans,
		leaves,
		sources,
		sinks,
		density,
		avgDegree,
		mostConnected: argmax(ids, (id) => metrics.get(id)!.degree),
		bridge: argmax(ids, (id) => metrics.get(id)!.betweenness),
		bestStart: argmax(ids, (id) => metrics.get(id)!.closeness),
		authoritative: argmax(ids, (id) => metrics.get(id)!.pagerank)
	};
}

/** Shortest path (BFS, undirected) between two nodes, as an id list, or null. */
export function shortestPath(
	nodes: GNode[],
	edges: GEdge[],
	from: string,
	to: string
): string[] | null {
	if (from === to) return [from];
	const { undirected } = adjacency(
		nodes.map((n) => n.id),
		edges
	);
	if (!undirected.has(from) || !undirected.has(to)) return null;
	const prev = new Map<string, string | null>([[from, null]]);
	const queue = [from];
	while (queue.length) {
		const v = queue.shift()!;
		for (const w of undirected.get(v)!) {
			if (!prev.has(w)) {
				prev.set(w, v);
				if (w === to) {
					const path = [w];
					let cur: string | null = v;
					while (cur !== null) {
						path.unshift(cur);
						cur = prev.get(cur)!;
					}
					return path;
				}
				queue.push(w);
			}
		}
	}
	return null;
}
