from utils import (ANCIENT_CHECKPOINTS_TABLE, TOWER_CHECKPOINTS_TABLE,
                   TOWER_LOCATIONS_TABLE, TREASURE_ROOMS_TABLE,
                   ENTRANCE_REACHABILITY_TABLE,
                   utilrandom as random)
from locationrandomizer import (get_locations, get_location, Location,
                                get_unused_locations, Entrance,
                                add_location_map, update_locations)
from formationrandomizer import get_fsets, get_formations
from chestrandomizer import ChestBlock
from itertools import izip_longest

SIMPLE, OPTIONAL, DIRECTIONAL = 's', 'o', 'd'
MAX_NEW_EXITS = 1000
MAX_NEW_MAPS = None  # 23: 6 more for fanatics tower, 1 more for bonus
ANCIENT = None
PROTECTED = [0, 1, 2, 3, 0xB, 0xC, 0xD, 0x11,
             0x37, 0x81, 0x82, 0x88, 0x9c, 0xb6, 0xb8, 0xbd, 0xbe,
             0xd2, 0xd3, 0xd4, 0xd5, 0xd7, 0xfe, 0xff,
             0x100, 0x102, 0x103, 0x104, 0x105, 0x10c, 0x12e,
             0x131, 0x132,  # Tzen WoR?
             0x139, 0x13a, 0x13b, 0x13c,  # Phoenix Cave
             0x13d,  # Three Stooges
             0x143, 0x144,  # Albrook
             0x154, 0x155, 0x157, 0x158,  # Thamasa
             0xe7, 0xe9, 0xea, 0xeb,  # opera with dancers?
             0x189, 0x18a,  # floating continent
             0x150, 0x164, 0x165, 0x19a, 0x19e]
PROTECTED += range(359, 371)  # Fanatics Tower
PROTECTED += range(382, 387)  # Sealed Gate
FIXED_ENTRANCES, REMOVE_ENTRANCES = [], []

locexchange = {}
old_entrances = {}
towerlocids = [int(line.strip(), 0x10) for line in open(TOWER_LOCATIONS_TABLE)]
map_bans = []
newfsets = {}
clusters = None


def remap_maps(routes):
    conlinks = []
    cononeways = []
    conentrances = []
    conclusters = []
    for route in routes:
        conlinks.extend(route.consolidated_links)
        cononeways.extend(route.consolidated_oneways)
        conentrances.extend(route.consolidated_entrances)
        conclusters.extend(route.consolidated_clusters)
        conclusters = sorted(set(conclusters), key=lambda c: c.clusterid)

    if ANCIENT:
        unused_maps = [l.locid for l in get_locations()
                       if l.locid not in towerlocids
                       and l.locid not in PROTECTED]
        rest_maps = [l.locid for l in get_unused_locations() if l.locid != 414]
    else:
        unused_maps = [l.locid for l in get_unused_locations()]
        rest_maps = []

    for cluster in conclusters:
        if not isinstance(cluster, RestStop):
            continue
        locid = cluster.locid
        newlocid = rest_maps.pop()
        locexchange[(locid, locid)] = newlocid
        try:
            unused_maps.remove(newlocid)
        except:
            import pdb; pdb.set_trace()

    for cluster in conclusters:
        if isinstance(cluster, RestStop):
            continue

        locid = cluster.locid
        if (locid, cluster.clusterid) in locexchange:
            continue

        locclusters = [c for c in conclusters if
                       not isinstance(c, RestStop) and c.locid == locid]
        if locid in towerlocids:
            for c in locclusters:
                locexchange[(locid, c.clusterid)] = locid
        else:
            location = get_location(locid)
            newlocid = unused_maps.pop()
            if location.longentrances:
                locexchange[(locid, cluster.clusterid)] = newlocid
            else:
                for c in locclusters:
                    locexchange[(locid, c.clusterid)] = newlocid

    newlocations = []
    for newlocid in sorted(set(locexchange.values())):
        keys = [key for (key, value) in locexchange.items()
                if value == newlocid]
        assert len(set([a for (a, b) in keys])) == 1
        copylocid = keys[0][0]
        if copylocid >= 1000:
            cluster = [c for c in conclusters if c.locid == copylocid][0]
            copylocid = 413
            location = get_location(413)
            newlocation = Location(locid=newlocid, dummy=True)
            newlocation.copy(location)
            newlocation.events = []
            newlocation.npcs = []
            newlocation.entrance_set.entrances = []
            newlocation.restrank = cluster.rank
        else:
            location = get_location(copylocid)
            entrances = location.entrances
            newlocation = Location(locid=newlocid, dummy=True)
            newlocation.copy(location)
            newlocation.events = []
            newlocation.npcs = []
            newlocation.entrance_set.entrances = []
            fixed = [e for e in entrances
                     if (e.location.locid, e.entid) in FIXED_ENTRANCES]
            newlocation.entrance_set.entrances.extend(fixed)

        locclusters = [c for c in conclusters if
                       locexchange[(c.locid, c.clusterid)] == newlocid]
        clustents = [e for c in locclusters for e in c.entrances]
        clustents = [e for e in clustents if e in conentrances]

        for ent in clustents:
            destent = [(a, b) for (a, b) in conlinks if ent in (a, b)]
            destent += [(a, b) for (a, b) in cononeways if ent == a]
            assert len(destent) == 1
            destent = destent[0]
            destent = [d for d in destent if d != ent][0]
            destclust = [c for c in conclusters
                         if destent in c.entrances]
            assert len(destclust) == 1
            destclust = destclust[0]
            newdestlocid = locexchange[(destclust.locid, destclust.clusterid)]
            if destent.location.locid >= 1000:
                destloc = get_location(413)
                destent = [d for d in destloc.entrances if d.entid == 3][0]
            else:
                destloc = get_location(destent.location.locid)
                destent = [d for d in destloc.entrances
                           if d.entid == destent.entid][0]
            mirror = destent.mirror
            if mirror:
                dest = mirror.dest & 0xFE00
                destx, desty = mirror.destx, mirror.desty
                if abs(destx - destent.x) + abs(desty - destent.y) > 3:
                    mirror = None

            if not mirror:
                dest, destx, desty = 0, destent.x, destent.y
            dest &= 0x3DFF

            dest |= newdestlocid
            entrance = Entrance()
            entrance.x, entrance.y = ent.x, ent.y
            entrance.dest, entrance.destx, entrance.desty = dest, destx, desty
            entrance.set_location(newlocation)
            newlocation.entrance_set.entrances.append(entrance)

        newlocation.setid = 0
        newlocation.ancient_rank = 0
        newlocation.copied = copylocid
        newlocations.append(newlocation)

    locations = get_locations()
    newlocids = [l.locid for l in newlocations]
    assert len(newlocids) == len(set(newlocids))
    for location in newlocations:
        for e in location.entrances:
            if (location.locid, e.entid) not in FIXED_ENTRANCES:
                assert e.dest & 0x1FF in newlocids
        assert location not in locations
        if location.locid not in towerlocids:
            location.entrance_set.convert_longs()

    # XXX: Unnecessary???
    for i, loc in enumerate(newlocations):
        if loc.locid in towerlocids:
            oldloc = get_location(loc.locid)
            oldloc.entrance_set.entrances = loc.entrances
            oldloc.ancient_rank = loc.ancient_rank
            oldloc.copied = oldloc.locid
            newlocations[i] = oldloc

    ranked_clusters = []
    for n in range(len(routes[0].segments)):
        rankedcsets = [route.segments[n].ranked_clusters for route in routes]
        for tricluster in izip_longest(*rankedcsets, fillvalue=None):
            tricluster = list(tricluster)
            random.shuffle(tricluster)
            for cluster in tricluster:
                if cluster is None:
                    continue
                if cluster.locid not in ranked_clusters:
                    ranked_clusters.append(cluster)

    ranked_locations = []
    for cluster in ranked_clusters:
        locid, clusterid = cluster.locid, cluster.clusterid
        newlocid = locexchange[locid, clusterid]
        newloc = [l for l in newlocations if l.locid == newlocid][0]
        if newloc not in ranked_locations:
            ranked_locations.append(newloc)
    assert len(set(ranked_locations)) == len(set(newlocations))

    ranked_locations = [l for l in ranked_locations
                        if not hasattr(l, "restrank")]
    for i, loc in enumerate(ranked_locations):
        loc.ancient_rank = i
        loc.make_tower_basic()

    return newlocations, unused_maps


class Cluster:
    def __init__(self, locid, clusterid):
        self.locid = locid
        self.clusterid = clusterid
        self.entrances = []

    @property
    def singleton(self):
        return len(self.entrances) == 1

    @property
    def has_adjacent_entrances(self):
        for e1 in self.entrances:
            for e2 in self.entrances:
                if e1 == e2:
                    continue
                if e1.x == e2.x and e1.y == e2.y:
                    raise Exception("ERROR: Overlapping entrances")
                if ((e1.x == e2.x and abs(e1.y - e2.y) == 1) or
                        (abs(e1.x - e2.x) == 1 and e1.y == e2.y)):
                    return True
        return False

    def add_entrance(self, entrance):
        e = Entrance()
        e.copy(entrance)
        self.entrances.append(e)

    @property
    def entids(self):
        return [e.entid for e in self.entrances]

    @property
    def free_entrances(self):
        free = [e for e in self.entrances if (e.location.locid, e.entid) not in
                FIXED_ENTRANCES + REMOVE_ENTRANCES]
        return free

    def __repr__(self):
        display = "; ".join([str(e) for e in self.entrances])
        return display


class RestStop(Cluster):
    counter = 0

    def __init__(self, rank):
        self.rank = rank
        e = Entrance()
        e.location = Location(1000 + RestStop.counter, dummy=True)
        self.locid = e.location.locid
        self.clusterid = self.locid
        e.x, e.y = 48, 21
        e.dest, e.destx, e.desty = 0, 0, 0
        e.entid = None
        self.entrances = [e]
        RestStop.counter += 1

    def __repr__(self):
        return "Rest stop rank %s" % self.rank


def get_clusters():
    global clusters
    if clusters is not None:
        return clusters

    clusters = []
    for i, line in enumerate(open(ENTRANCE_REACHABILITY_TABLE)):
        locid, entids = line.strip().split(':')
        locid = int(locid)
        entids = map(int, entids.split(','))
        loc = get_location(locid)
        entrances = [e for e in loc.entrances if e.entid in entids]
        c = Cluster(locid=locid, clusterid=i)
        for e in entrances:
            c.add_entrance(e)
        c.original_entrances = list(c.entrances)
        clusters.append(c)

    return get_clusters()


def get_cluster(locid, entid):
    for c in get_clusters():
        if c.locid == locid and entid in c.entids:
            return c


class Segment:
    def __init__(self, checkpoints):
        self.clusters = []
        self.entids = []
        for locid, entid in checkpoints:
            if locid == "R":
                c = RestStop(rank=entid)
                self.clusters.append(c)
                self.entids.append(None)
            else:
                c = get_cluster(locid, entid)
                assert c is not None
                self.clusters.append(c)
                self.entids.append(entid)
            c.exiting, c.entering = False, False
        self.intersegments = [InterSegment() for c in self.clusters[:-1]]
        self.original_clusters = list(self.clusters)
        self.oneway_entrances = []

    @property
    def ranked_clusters(self):
        startclust = self.clusters[0]
        done = set([startclust])
        ranked = []
        if startclust not in ranked:
            ranked.append(startclust)
        while True:
            ents = [e for c in done for e in c.entrances]
            relevant_links = [(a, b) for (a, b) in self.consolidated_links
                              if a in ents or b in ents]
            new_ents = set([])
            for a, b in relevant_links:
                if a not in ents:
                    new_ents.add(a)
                if b not in ents:
                    new_ents.add(b)
            if not new_ents:
                break
            newclusts = [c for c in self.consolidated_clusters
                         if set(c.entrances) & new_ents]
            done |= set(newclusts)
            random.shuffle(newclusts)
            for c in newclusts:
                if c not in ranked:
                    ranked.append(c)

        if set(self.consolidated_clusters) != set(ranked):
            import pdb; pdb.set_trace()
        return ranked

    @property
    def consolidated_links(self):
        links = list(self.links)
        for inter in self.intersegments:
            links.extend(inter.links)
        return links

    @property
    def consolidated_clusters(self):
        clusters = list(self.clusters)
        for inter in self.intersegments:
            clusters.extend(inter.clusters)
        return clusters

    @property
    def consolidated_entrances(self):
        links = self.consolidated_links
        linked_entrances = []
        for a, b in links:
            linked_entrances.append(a)
            linked_entrances.append(b)
        for e, _ in self.oneway_entrances:
            linked_entrances.append(e)
        return linked_entrances

    def check_links(self):
        linked_entrances = self.consolidated_entrances
        assert len(linked_entrances) == len(set(linked_entrances))

    def interconnect(self):
        links = []
        for segment in self.intersegments:
            segment.interconnect()
        for i, (a, b) in enumerate(zip(self.clusters, self.clusters[1:])):
            aid = self.entids[i]
            bid = self.entids[i+1]
            if a.singleton:
                acands = a.entrances
            elif i == 0:
                acands = [e for e in a.entrances if e.entid == aid]
            else:
                acands = [e for e in a.entrances if e.entid != aid]
            aent = random.choice(acands)
            bcands = [e for e in b.entrances if e.entid == bid]
            bent = bcands[0]
            inter = self.intersegments[i]
            if a.singleton:
                excands = inter.get_external_candidates(num=3, test=True)
                previnter = self.intersegments[i-1] if i > 0 else None
                if excands is None and previnter is not None:
                    excands = previnter.get_external_candidates(num=1)
                if excands is None or len(excands) == 3:
                    excands = inter.get_external_candidates(num=1)
                if excands is None:
                    raise Exception("Routing error.")
                links.append((aent, excands[0]))
                a.entering, a.exiting = True, True
                if previnter and not previnter.empty:
                    # TODO: Sometimes this fails
                    for j in range(i, len(self.intersegments)):
                        nextinter = self.intersegments[j]
                        if nextinter.empty:
                            continue
                        c = previnter.get_external_candidates(num=1)[0]
                        d = nextinter.get_external_candidates(num=1)[0]
                        links.append((c, d))
                        break
                    else:
                        raise Exception("No exit segment available.")
            elif not inter.empty:
                if not b.singleton:
                    excands = inter.get_external_candidates(num=2)
                    if excands is None:
                        raise Exception("No exit segment available. (2)")
                    random.shuffle(excands)
                    links.append((bent, excands[1]))
                    b.entering = True
                else:
                    excands = inter.get_external_candidates(num=1)
                links.append((aent, excands[0]))
                a.exiting = True
            elif (inter.empty and not b.singleton):
                links.append((aent, bent))
                a.exiting = True
                b.entering = True
            elif (inter.empty and b.singleton):
                inter2 = self.intersegments[i+1]
                assert not inter2.empty
                excands = inter2.get_external_candidates(num=1)
                links.append((aent, excands[0]))
                a.exiting = True
            else:
                import pdb; pdb.set_trace()
                assert False

        for i, a in enumerate(self.clusters):
            aid = self.entids[i]
            if not (a.entering or i == 0):
                if a.singleton:
                    aent = a.entrances[0]
                else:
                    acands = [e for e in a.entrances if e.entid == aid]
                    aent = acands[0]
                while i > 0:
                    inter = self.intersegments[i-1]
                    if not inter.empty:
                        break
                    i += -1
                if inter.empty:
                    raise Exception("Routing error.")
                excands = inter.get_external_candidates(num=1)
                links.append((aent, excands[0]))
                a.entering = True

        self.links = links
        self.check_links()

    def fill_out(self):
        entrances = list(self.consolidated_entrances)
        seen = []
        for cluster, inter in zip(self.clusters, self.intersegments):
            if cluster.locid == 334 and 11 in cluster.entids:
                additionals = [e for e in cluster.entrances
                               if e not in self.consolidated_entrances]
                assert len(additionals) == 1
                extra = inter.fill_out(additionals[0])
            else:
                extra = inter.fill_out()
            seen.extend([e for e in cluster.entrances if e in entrances])
            for c in inter.clusters:
                seen.extend([e for e in c.entrances if e in entrances])
            if extra is not None:
                backtrack = random.choice(seen)
                self.oneway_entrances.append((extra, backtrack))

    def add_cluster(self, cluster, need=False):
        self.entids.append(None)
        self.clusters.append(cluster)
        if need:
            self.need -= len(cluster.entrances) - 2

    @property
    def free_entrances(self):
        free = []
        for (entid, cluster) in zip(self.entids, self.clusters):
            if entid is not None:
                clustfree = cluster.free_entrances
                clustfree = [e for e in clustfree if e.entid != entid]
                free.extend(clustfree)
        return free

    @property
    def reserved_entrances(self):
        free = self.free_entrances
        reserved = []
        for cluster in self.clusters:
            if isinstance(cluster, Cluster):
                reserved.extend([e for e in cluster.entrances
                                 if e not in free])
        return reserved

    def determine_need(self):
        for segment in self.intersegments:
            segment.need = 0
        for index, cluster in enumerate(self.clusters):
            if len(cluster.entrances) == 1:
                indexes = [i for i in [index-1, index]
                           if 0 <= i < len(self.intersegments)]
                for i in indexes:
                    self.intersegments[i].need += 1

    def __repr__(self):
        display = ""
        for i, cluster in enumerate(self.clusters):
            entid = self.entids[i]
            if entid is None:
                entid = '?'
            display += "%s %s\n" % (entid, cluster)
            if not isinstance(self, InterSegment):
                if i < len(self.intersegments):
                    display += str(self.intersegments[i]) + "\n"
        display = display.strip()
        if not display:
            display = "."
        if not isinstance(self, InterSegment):
            display += "\nCONNECT %s" % self.consolidated_links
            display += "\nONE-WAY %s" % self.oneway_entrances
        return display


class InterSegment(Segment):
    def __init__(self):
        self.clusters = []
        self.entids = []
        self.links = []
        self.linked_edge = []

    @property
    def empty(self):
        return len(self.clusters) == 0

    @property
    def linked_entrances(self):
        linked = []
        for a, b in self.links:
            linked.append(a)
            linked.append(b)
        for e in self.linked_edge:
            linked.append(e)
        return linked

    def get_external_candidates(self, num=2, test=False):
        if not self.clusters:
            return None
        candidates = []
        linked_clusters = []
        for e in self.linked_entrances:
            for c in self.clusters:
                if e in c.entrances:
                    linked_clusters.append(c)
        done_clusts = set([])
        done_ents = set(self.linked_entrances)
        for _ in xrange(num):
            candclusts = [c for c in self.clusters if c not in done_clusts]
            if not candclusts:
                candclusts = self.clusters
            candclusts = [c for c in candclusts if set(c.entrances)-done_ents]
            if not candclusts:
                candclusts = [c for c in self.clusters if c not in done_clusts
                              and set(c.entrances)-done_ents]
                if not candclusts:
                    candclusts = [c for c in self.clusters
                                  if set(c.entrances)-done_ents]
            if candclusts and linked_clusters:
                lowclust = min(candclusts,
                               key=lambda c: linked_clusters.count(c))
                lowest = linked_clusters.count(lowclust)
                candclusts = [c for c in candclusts
                              if linked_clusters.count(c) == lowest]
                assert lowclust in candclusts
            try:
                chosen = random.choice(candclusts)
            except IndexError:
                return None
            done_clusts.add(chosen)
            chosen = random.choice([c for c in chosen.entrances
                                    if c not in done_ents])
            done_ents.add(chosen)
            candidates.append(chosen)
        if not test:
            self.linked_edge.extend(candidates)
        return candidates

    def interconnect(self):
        self.links = []
        if len(self.clusters) < 2:
            return

        starter = max(self.clusters, key=lambda c: len(c.entrances))
        while True:
            links = []
            done_ents = set([])
            done_clusts = set([starter])
            clusters = self.clusters
            random.shuffle(clusters)
            for c in clusters:
                if c in done_clusts:
                    continue
                candidates = [c2 for c2 in done_clusts
                              if set(c2.entrances) - done_ents]
                if not candidates:
                    break
                chosen = random.choice(candidates)
                acands = [e for e in c.entrances if e not in done_ents]
                bcands = [e for e in chosen.entrances if e not in done_ents]
                a, b = random.choice(acands), random.choice(bcands)
                done_clusts.add(c)
                done_ents.add(a)
                done_ents.add(b)
                links.append((a, b))
            if done_clusts == set(self.clusters):
                break
        self.links = links

    def fill_out(self, additional=None):
        linked = self.linked_entrances
        links = []
        unlinked = []
        for cluster in self.clusters:
            entrances = [e for e in cluster.entrances if e not in linked]
            random.shuffle(entrances)
            if ANCIENT:
                unlinked.extend(entrances)
            else:
                if len(cluster.entrances) <= 4:
                    unlinked.extend(entrances)
                else:
                    diff = len(cluster.entrances) - len(entrances)
                    if diff < 3:
                        remaining = 3 - diff
                        unlinked.extend(entrances[:remaining])

        if additional:
            unlinked.append(additional)

        if not unlinked:
            return
        random.shuffle(unlinked)

        locids = [e.location.locid for e in unlinked]
        maxlocid = max(locids, key=lambda l: locids.count(l))
        mosts = [e for e in unlinked if e.location.locid == maxlocid]
        lesses = [e for e in unlinked if e not in mosts]
        for m in mosts:
            if not lesses:
                break
            l = random.choice(lesses)
            links.append((m, l))
            lesses.remove(l)
            unlinked.remove(l)
            unlinked.remove(m)

        extra = None
        while unlinked:
            if len(unlinked) == 1:
                extra = unlinked[0]
                break
            u1 = unlinked.pop()
            u2 = unlinked.pop()
            links.append((u1, u2))

        self.links += links
        return extra


class Route:
    def __init__(self, segments):
        self.segments = segments

    @property
    def ranked_clusters(self):
        ranked = []
        for s in self.segments:
            ranked.extend(s.ranked_clusters)
        return ranked

    def determine_need(self):
        for segment in self.segments:
            segment.determine_need()

    @property
    def consolidated_oneways(self):
        consolidated = []
        for segment in self.segments:
            consolidated.extend(segment.oneway_entrances)
        return consolidated

    @property
    def consolidated_clusters(self):
        consolidated = []
        for segment in self.segments:
            consolidated.extend(segment.consolidated_clusters)
        return consolidated

    @property
    def consolidated_links(self):
        consolidated = []
        for segment in self.segments:
            consolidated.extend(segment.consolidated_links)
        return consolidated

    @property
    def consolidated_entrances(self):
        consolidated = []
        for segment in self.segments:
            consolidated.extend(segment.consolidated_entrances)
        return consolidated

    def check_links(self, links=None):
        for segment in self.segments:
            segment.check_links()
        linked = []
        for a, b in self.consolidated_links:
            linked.append(a)
            linked.append(b)
        assert len(linked) == len(set(linked))

    def __repr__(self):
        display = "\n---\n".join([str(s) for s in self.segments])

        return display


def parse_checkpoints():
    if ANCIENT:
        checkpoints = ANCIENT_CHECKPOINTS_TABLE
    else:
        checkpoints = TOWER_CHECKPOINTS_TABLE

    def ent_text_to_ints(room, single=False):
        locid, entids = room.split(':')
        locid = int(locid)
        if '|' in entids:
            entids = entids.split('|')
        elif ',' in entids:
            entids = entids.split(',')
        elif '>' in entids:
            entids = entids.split('>')[:1]
        else:
            entids = [entids]
        entids = map(int, entids)
        if single:
            assert len(entids) == 1
            entids = entids[0]
        return locid, entids

    done, fixed, remove, oneway = [], [], [], []
    routes = [list([]) for _ in xrange(3)]
    for line in open(checkpoints):
        line = line.strip()
        if not line or line[0] == '#':
            continue
        if line[0] == 'R':
            rank = int(line[1:])
            for route in routes:
                route[-1].append(("R", rank))
        elif line[0] == '&':
            locid, entids = ent_text_to_ints(line[1:])
            for e in entids:
                fixed.append((locid, e))
        elif line[0] == '-':
            locid, entids = ent_text_to_ints(line[1:])
            for e in entids:
                remove.append((locid, e))
        elif '>>' in line:
            line = line.split('>>')
            line = [ent_text_to_ints(s, single=True) for s in line]
            first, second = tuple(line)
            oneway.append((first, second))
        else:
            if line.startswith("!"):
                line = line.strip("!")
                for route in routes:
                    route.append([])
            elif line.startswith("$"):
                line = line.strip("$")
                for route in routes:
                    subroute = route[-1]
                    head, tail = subroute[0], subroute[1:]
                    random.shuffle(tail)
                    route[-1] = [head] + tail
            else:
                random.shuffle(routes)
            rooms = line.split(',')
            chosenrooms = []
            for room in rooms:
                locid, entids = ent_text_to_ints(room)
                candidates = [(locid, entid) for entid in entids]
                candidates = [c for c in candidates if c not in done]
                chosen = random.choice(candidates)
                chosenrooms.append(chosen)
                done.append(chosen)
            for room, route in zip(chosenrooms, routes):
                route[-1].append(room)

    for first, second in oneway:
        done = False
        for route in routes:
            for subroute in route:
                if first in subroute:
                    index = subroute.index(first)
                    index = random.randint(1, index+1)
                    subroute.insert(index, second)
                    done = True
        if not done:
            raise Exception("Unknown oneway rule")

    for route in routes:
        for i in range(len(route)):
            route[i] = Segment(route[i])

    for index in range(len(routes)):
        routes[index] = Route(routes[index])

    FIXED_ENTRANCES.extend(fixed)
    REMOVE_ENTRANCES.extend(remove)
    return routes


def assign_maps(routes):
    clusters = get_clusters()
    new_clusters = clusters
    for route in routes:
        for segment in route.segments:
            for cluster in segment.clusters:
                if cluster in new_clusters:
                    new_clusters.remove(cluster)

    new_clusters = [c for c in new_clusters if not c.has_adjacent_entrances]

    # first phase - bare minimum
    if not ANCIENT:
        max_new_maps = 23
    else:
        #max_new_maps = 313
        max_new_maps = 50
    best_clusters = [c for c in new_clusters if len(c.entrances) >= 3]
    while True:
        random.shuffle(best_clusters)
        done_maps, done_clusters = set([]), set([])
        for cluster in best_clusters:
            if cluster.locid in done_maps:
                continue
            chosen = None
            for route in routes:
                for segment in route.segments:
                    for inter in segment.intersegments:
                        if chosen is None or chosen.need < inter.need:
                            chosen = inter
            if chosen.need > 0:
                chosen.add_cluster(cluster, need=True)
                done_maps.add(cluster.locid)
                done_clusters.add(cluster.clusterid)
        if len(done_maps) <= max_new_maps:
            break
        else:
            for route in routes:
                for segment in route.segments:
                    segment.intersegments = [InterSegment()
                                             for _ in segment.intersegments]

    # second phase -supplementary
    random.shuffle(new_clusters)
    for cluster in new_clusters:
        if cluster.clusterid in done_clusters:
            continue
        if cluster.locid not in towerlocids:
            if (cluster.locid not in done_maps
                    and len(done_maps) >= max_new_maps):
                continue
            if (cluster.locid in done_maps and len(done_maps) >= max_new_maps
                    and get_location(cluster.locid).longentrances):
                continue
        rank = None
        if cluster.locid in done_maps:
            for route in routes:
                for segment in route.segments:
                    for c1 in segment.clusters:
                        if c1.locid == cluster.locid:
                            temp = route.segments.index(segment)
                            if rank is None:
                                rank = temp
                            else:
                                rank = min(rank, temp)
                    for inter in segment.intersegments:
                        for c2 in inter.clusters:
                            if c2.locid == cluster.locid:
                                temp = route.segments.index(segment)
                                if rank is None:
                                    rank = temp
                                else:
                                    rank = min(rank, temp)
        if len(cluster.entrances) == 1:
            candidates = []
            for route in routes:
                for (i, segment) in enumerate(route.segments):
                    if rank is not None and i != rank:
                        continue
                    for inter in segment.intersegments:
                        if inter.need < 0:
                            candidates.append(inter)
            if candidates:
                chosen = random.choice(candidates)
                chosen.add_cluster(cluster, need=True)
                done_maps.add(cluster.locid)
                done_clusters.add(cluster.clusterid)
        elif len(cluster.entrances) >= 2:
            route = random.choice(routes)
            if rank is not None:
                segment = route.segments[rank]
            else:
                segment = random.choice(route.segments)
            chosen = random.choice(segment.intersegments)
            chosen.add_cluster(cluster, need=True)
            done_maps.add(cluster.locid)
            done_clusters.add(cluster.clusterid)

    for route in routes:
        for segment in route.segments:
            segment.interconnect()


def randomize_tower(filename, ancient=False):
    global ANCIENT
    ANCIENT = ancient
    routes = parse_checkpoints()
    for route in routes:
        route.determine_need()
    assign_maps(routes)
    for route in routes:
        for segment in route.segments:
            segment.fill_out()
    for route in routes:
        route.check_links()

    newlocations, unused_maps = remap_maps(routes)
    update_locations(newlocations)

    for route in routes:
        print route
        print
        print
        print

    return routes


if __name__ == "__main__":
    from randomizer import get_monsters
    get_monsters(filename="program.rom")
    get_formations(filename="program.rom")
    get_fsets(filename="program.rom")
    get_locations(filename="program.rom")

    routes = randomize_tower("program.rom", ancient=True)
    for route in routes:
        print route
        print
        print
