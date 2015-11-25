import json
from decimal import Decimal

import psycopg2


class BundestagMembers(object):
    def __init__(self):
        self.conn = psycopg2.connect("host=localhost dbname=wahlsystem user=postgres password=Password01")
        self.cur = self.conn.cursor()
        self.conn.autocommit = True

    def get_members(self, election):
        self.cur.execute(
            """SELECT mb.firstname, mb.lastname, mb.party, mb.bundesland, dw.wahlkreis, w.name
               FROM members_of_bundestag mb
               LEFT JOIN (directmandate_winners dw
                          JOIN wahlkreis w
                          ON w.id = dw.wahlkreis)
                ON mb.id = dw.candidate
                AND mb.election = dw.election
                WHERE mb.election = %s
               ORDER BY mb.lastname""", (election,))

        members = []

        for member in self.cur.fetchall():
            members.append({
                'firstname': member[0],
                'lastname': member[1],
                'party': member[2],
                'bundesland': member[3],
                'wk_id': member[4],
                'wk_name': member[5]
            })

        return members


class Wahlkreise(object):
    def __init__(self):
        self.conn = psycopg2.connect("host=localhost dbname=wahlsystem user=postgres password=Password01")
        self.cur = self.conn.cursor()
        self.conn.autocommit = True

    def get_overview(self, election):

        self.cur.execute(
            """
            SELECT wk.id, wk.name, p.name, zw_party
            FROM wahlkreis wk
            LEFT JOIN directmandate_winners dw ON dw.wahlkreis = wk.id
            LEFT JOIN party p on dw.party = p.id
            LEFT JOIN (SELECT zw.election, zw.wahlkreis, p2.name as zw_party FROM zweitstimme_results zw , party p2
                                                                   WHERE p2.id = zw.party
                                                                   AND NOT EXISTS (SELECT * FROM zweitstimme_results zw2
                                                                   WHERE zw2.wahlkreis = zw.wahlkreis
                                                                   AND zw2.election = zw.election
                                                                   AND zw2.count > zw.count)) as zweitstimme
            ON zweitstimme.wahlkreis = wk.id
            AND p.id = dw.party
            AND zweitstimme.election = dw.election
            WHERE dw.election = %s
            ORDER BY wk.id
            """, (election,)
        )

        wahlkreise = []

        for wk in self.cur.fetchall():
            wahlkreise.append({
                'wk_id': wk[0],
                'wk_name': wk[1],
                'wk_first': wk[2],
                'wk_second': wk[3]
            })

        return wahlkreise

    def get_details(self, wk_id, election):

        # Get infos on wahlkreis and direct mandate winner
        self.cur.execute(
            """SELECT w.id, w.name, c.firstname, c.lastname
                FROM wahlkreis w, directmandate_winners dw, candidate c
                WHERE dw.wahlkreis = w.id
                AND c.id = dw.candidate
                AND w.id = %s""",
            (wk_id,)
        )

        # TODO: Was wenn party = None?
        wahlkreis = self.cur.fetchone()

        # Get the candidates trying to get a direct mandate
        wk_candidates = []

        self.cur.execute(
            """
            SELECT c.firstname, c.lastname, p.name, er.count,
                    round(er.count / votes.votes * 100,1) as percentage
            FROM directmandate d left join party p on p.id = d.party, candidate c, erststimme_results er,
                (select sum(count) as votes, er2.election, er2.wahlkreis
                                      from erststimme_results er2
                                      group by er2.election, er2.wahlkreis) as votes
            WHERE d.candidate = c.id
            AND er.candidate = c.id
            AND er.election = d.election
            AND votes.election = d.election
            AND votes.wahlkreis = d.wahlkreis
            AND d.election = %s
            AND d.wahlkreis = %s
            order by er.count desc
            """,
            (election, wk_id)
        )
        for candidate in self.cur.fetchall():
            wk_candidates.append({
                'c_name': candidate[0] + ' ' + candidate[1],
                'c_pname': candidate[2],
                'c_votes': candidate[3],
                'c_percentage': candidate[4]
            })

        # Get the results of the parties
        wk_parties = []
        self.cur.execute(
            """
            SELECT p.name, zr.count, round(zr.count / votes.votes * 100,1) as percentage
            FROM zweitstimme_results zr, party p,
              (select sum(count) as votes, zr2.election, zr2.wahlkreis
              from zweitstimme_results zr2
              group by zr2.election, zr2.wahlkreis) as votes
            WHERE zr.party = p.id
            AND zr.election = votes.election
            AND zr.wahlkreis = votes.wahlkreis
            AND zr.wahlkreis = %s
            AND zr.election = %s
            order by zr.count desc
            """,
            (wk_id, election)
        )
        for party in self.cur.fetchall():
            wk_parties.append({
                'p_name': party[0],
                'p_votes': party[1],
                'p_percentage': party[2]
            })

        # Get wahlbeteiligung
        self.cur.execute(
            """
            SELECT w.wahlbeteiligung
            FROM wahlbeteiligung w
            WHERE w.wahlkreis = %s
            AND w.election = 2
            """,
            (wk_id,)
        )
        wahlbeteiligung = self.cur.fetchone()

        return {'wk_id': wahlkreis[0],
                'wk_name': wahlkreis[1],
                'winner_fn': wahlkreis[2],
                'winner_ln': wahlkreis[3],
                'wahlbeteiligung': wahlbeteiligung[0],
                'candidates': wk_candidates,
                'parties': wk_parties}


class Overview(object):
    def __init__(self):
        self.conn = psycopg2.connect("host=localhost dbname=wahlsystem user=postgres password=Password01")
        self.cur = self.conn.cursor()
        self.conn.autocommit = True
        self.color_mapping = {
            'CDU': 'black',
            'SPD': 'red',
            'FDP': 'yellow',
            'CSU': 'black',
            'GRÜNE': 'green',
            'DIE LINKE': 'purple'
        }
        self.interesting_parties = [
            'CDU', 'FDP', 'CSU', 'SPD', 'GRÜNE', 'DIE LINKE', 'AfD', 'PIRATEN'
        ]

    def get_composition(self, election):

        self.cur.execute(
            """SELECT p.name, cast(seats as int)
               FROM seats_by_party sp, party p
               WHERE p.id = sp.party
               AND election = %s
               ORDER BY seats desc
            """, (election,)
        )

        data = []
        for datapoint in self.cur.fetchall():
            data.append({'name': datapoint[0],
                         'y': datapoint[1],
                         'color': self.color_mapping[datapoint[0]]})
        return data

    def get_percentages(self, election):

        self.cur.execute(
            """
            SELECT p.name, round((v.votes / t.total * 100),1) as percentage
            FROM votesbyparty v, party p, totalvotes t
            WHERE v.party = p.id
            AND v.election = t.election
            AND v.election = %s
            ORDER BY percentage DESC
            """, (election,)
        )

        results = self.cur.fetchall()

        graphDef = []
        for year in [2009, 2013]:
            graphDef.append({
                "index": (year - 2009) // 4,  # 0,1,... HACK
                "colorbyPoint": True,
                "name": year,
                "data": [[mapping[0], mapping[1]] for mapping in results if mapping[0] in self.interesting_parties]
            })
        return json.dumps(graphDef, cls=DecimalEncoder)


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return json.JSONEncoder.default(self, obj)


class ClosestWinners(object):
    def __init__(self):
        self.conn = psycopg2.connect("host=localhost dbname=wahlsystem user=postgres password=Password01")
        self.cur = self.conn.cursor()
        self.conn.autocommit = True

    def overview(self, election):
        self.cur.execute(
            """
            SELECT DISTINCT p.id, p.name
            FROM party p, zweitstimme_results zw
            WHERE p.id = zw.party
            AND zw.count > 0
            AND zw.election = %s
            ORDER BY name
            """, (election,)
        )

        parties = self.cur.fetchall()

        result = []

        for p in parties:
            result.append({
                'p_id': p[0],
                'p_name': p[1]
            })

        return result

    def get_winners(self, election, party):
        self.cur.execute(
            """
            SELECT cw.firstname, cw.lastname, cw.wahlkreis, cw.wname, cw.difference
            FROM closest_winners cw
            WHERE cw.party = %s
            AND cw.election = %s
            LIMIT 10
            """, (party, election))

        closest = []

        if self.cur.rowcount != 0:
            # if we have at least one winner in the party...
            closest = self.cur.fetchall()
        else:
            # otherwise get 10 losers...
            self.cur.execute(
                """
              SELECT cl.firstname, cl.lastname, cl.wahlkreis, cl.wname, cl.difference
              FROM closest_losers cl
              WHERE cl.party = %s
              AND cl.election = %s
              LIMIT 10
              """, (party, election))
            closest = self.cur.fetchall()

        result = []

        for person in closest:
            result.append({
                'firstname': person[0],
                'lastname': person[1],
                'wk_id': person[2],
                'wk_name': person[3],
                'difference': person[4]
            })

        self.cur.execute('SELECT name FROM party p WHERE p.id = %s', (party,))

        return {
            'people': result,
            'p_name': self.cur.fetchone()[0]
        }
