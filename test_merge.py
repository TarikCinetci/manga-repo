import gzip, unittest
import merge_repos as m

def src(sid, name, lang, home=None):
    f = [(1, 0, sid), (2, 2, name.encode()), (3, 2, lang.encode())]
    if home: f.append((4, 2, home.encode()))
    return m.encode(f)

def ext(name, pkg, ver, apk, icon, jar=None, sources=()):
    res = [(1, 2, apk.encode()), (2, 2, icon.encode())]
    if jar: res.append((501, 2, jar.encode()))
    f = [(1, 2, name.encode()), (2, 2, pkg.encode()), (3, 2, m.encode(res)), (5, 0, ver), (6, 2, b"1.0")]
    f += [(8, 2, s) for s in sources]
    return m.encode(f)

def index(records, wrapper=101):
    listing = m.encode([(1, 2, r) for r in records])
    return m.encode([(1, 2, b"x"), (wrapper, 2, listing)])

class MergeTest(unittest.TestCase):
    def test_merge_and_absolutize(self):
        a = index([ext("A", "pkg.a", 5, "apk/a.apk", "icon/a.png", "jar/a.jar", [src(1, "A", "tr", "site")]),
                   ext("B", "pkg.b", 1, "apk/b.apk", "icon/b.png")])
        b = index([ext("A2", "pkg.a", 9, "apk/a2.apk", "icon/a2.png", "jar/a2.jar"),
                   ext("C", "pkg.c", 3, "https://cdn.example/c.apk", "https://cdn.example/c.png")], wrapper=5)
        recs = m.merge([(a, "https://raw.githubusercontent.com/o/r/repo/index.pb"),
                        (b, "https://raw.githubusercontent.com/p/q/repo/index.pb")])
        self.assertEqual(len(recs), 3)
        by = {m.package_and_version(r)[0]: r for r in recs}
        self.assertEqual(m.package_and_version(by["pkg.a"])[1], 9)          # yüksek sürüm kazandı
        res = m.parse(m.get(m.parse(by["pkg.a"]), 3, 2))
        self.assertEqual(m.get(res, 501, 2), b"https://raw.githubusercontent.com/p/q/repo/jar/a2.jar")
        resb = m.parse(m.get(m.parse(by["pkg.b"]), 3, 2))
        self.assertEqual(m.get(resb, 1, 2), b"https://raw.githubusercontent.com/o/r/repo/apk/b.apk")
        resc = m.parse(m.get(m.parse(by["pkg.c"]), 3, 2))
        self.assertEqual(m.get(resc, 1, 2), b"https://cdn.example/c.apk")     # mutlak olan değişmez

    def test_round_trip_and_site_url(self):
        a = index([ext("A", "pkg.a", 5, "apk/a.apk", "i.png", None, [src(7, "A", "tr", "site")])])
        recs = m.merge([(a, "https://raw.githubusercontent.com/o/r/repo/index.pb")])
        out = m.build_index("Ad", "TR", recs)
        payload = gzip.decompress(out)
        again = m.extension_records(payload)
        self.assertEqual(len(again), 1)
        sources = [v for f, w, v in m.parse(again[0]) if f == 8]
        self.assertEqual(m.get(m.parse(sources[0]), 4, 2), b"https://raw.githubusercontent.com/o/r/repo/site")
        self.assertEqual(m.get(m.parse(payload), 1, 2), b"Ad")

    def test_normalize(self):
        self.assertEqual(m.normalize("https://github.com/keiyoushi/extensions/raw/repo/index.pb"),
                         "https://raw.githubusercontent.com/keiyoushi/extensions/repo/index.pb")

if __name__ == "__main__":
    unittest.main()
