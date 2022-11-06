import re, os, orodja, datetime


TAG_START = 10
NUM_TAGS = 50
STEVILO_STRANI = 25
STRANI_DIR = 'recepti_spletne-strani_id'
RECEPTI_DIR = 'recepti_spletne-strani'
RECEPTI_JSON = 'recepti.json'
KATEGORIJE_JSON = 'kategorije.json'
RK_JSON = 'rk.json'
SESTAVINE_JSON = 'sestavine.json'
RECEPTI_CSV = 'recepti.csv'
KATEGORIJE_CSV = 'kategorije.csv'
RK_CSV = 'rk.csv'
SESTAVINE_CSV = 'sestavine.csv'


def pridobi_id(tag):
    """Funkcija sprejme številko oznake in poišče id receptov, 
    ki se nahajajo na spletni strani pod to oznako, ter vrne množico idjev."""
    
    # Pripravimmo si prazeno množico idjev in definiramo niz, s katerim je v htmlju predstavljen id
    ids = set()
    vzorec_id = r'data-vars-tracking-id="recipe-(.*?)" '
    vzorec = re.compile(vzorec_id, flags=re.DOTALL)

    # Spletno stran shranimo v lokalno datoteko; če nas preusmeri na začetno stran, izvajanje funkcije prekinemo
    # Ker želimo shraniti vseh 25 strani te kategorije, naredimo zanko
    for i in range(STEVILO_STRANI):
        url = f"https://www.chefkoch.de/rs/s{i}t{tag}/Rezepte.html"
        path = os.path.join(STRANI_DIR, f"stran-{tag}-{i}.html")
        res = orodja.shrani_spletno_stran(url, path, f"https://www.chefkoch.de/rs/s0/Rezepte.html")

        # Preverimo, ali je shranjevanje uspelo
        if not os.path.isfile(path) or res == 404:
            return

        # Iz lokalnih (html) datotek preberemo podatke
        podatki_str = orodja.vsebina_datoteke(path)

        # Med podatki poiščemo id receptov
        id_n = set(re.findall(vzorec, podatki_str))
        if  not id_n:
            return ids
        ids = ids.union(id_n)

    return ids


def pridobi_podatke(recept, id):
    rx = re.compile(
        r'<h1 class="">(?P<title>.*?)</h1>.*?'
        r'<span class="recipe-preptime rds-recipe-meta__badge"><i class="material-icons"></i>\s*(?P<time>.*?) Min.\s*?</span>\s*?'
        r'<span class="recipe-difficulty rds-recipe-meta__badge"><i class="material-icons"></i>(?P<difficulty>.*?)</span>\s*?'
        r'<span class="recipe-date rds-recipe-meta__badge"><i class="material-icons"></i>(?P<date>.*?)</span>.*?'
        r'<table class="ingredients table-header" width="100%" cellspacing="0" cellpadding="0">(?P<sestavine>.*?)</table>\s*?<div>\s*?<div class.*?'
        r'<div class="ds-box recipe-tags">(?P<category>.*?)</amp-carousel>',
        re.DOTALL)
    data = re.search(rx, recept)
    sl = data.groupdict()


    # Na začetek slovarja dodamo id recepta.
    i = {'id': id}
    s = {**i, **sl}

    # Če ima recept objavljene naslednje podatke, dodamo še te.
    rx_d = {
        'calories': (r'<span class="recipe-kcalories rds-recipe-meta__badge"><i class="material-icons"></i>\s*(?P<calories>.*?) kcal\s*?</span>', ''),
        'info': (r'<p class="recipe-text ">(?P<info>.*?)</p>', ''),
        'num_comments': (r'<strong>(?P<num_comments>\d*?)</strong> Kommentar.*?', '0'),
        'num_votes': (r'<div class="ds-rating-count">\s*<span>.*?<span>(?P<num_votes>\d*)</span>.*?', '0'),
        'rating': (r'<span class="ds-sr-only">Durchschnittliche Bewertung:</span>\s*?<strong>(?P<rating>.*?)</strong>.*?', '0')
    }
    for kljuc, (v1, v2) in rx_d.items():
        r = re.compile(v1, re.DOTALL)
        desc = re.search(r, recept)
        if desc is not None:
            s[kljuc] = desc.group(kljuc)
        else:
            s[kljuc] = v2

    return s


def uredi_tezavnost(t: str, id):
    if t == 'simpel':
        return 0
    if t == 'normal':
        return 1
    if t == 'pfiffig':
        return 2
    else:
        print(f'Prišlo je do napake pri težavnosti recepta {id}. Vnešena vrednost: {t}')
        return ''


def izloci_sestavine(recept):
    vzorec_sestavine = re.compile(r'right\">\s*?<span>(<a.*?>)?(?P<sestavina>.*?)(</a>)?</span>')
    sestavine = [sestavina.group('sestavina') for sestavina in vzorec_sestavine.finditer(recept)]
    return sestavine


def izloci_kategorije(recept):
    vzorec_kategorije = re.compile(r'href=\"/rs/s\d*?t(?P<tag>\d*).*?data-vars-search-term=\"(?P<kat>.*?)\">')
    kategorije = []
    for kategorija in vzorec_kategorije.finditer(recept):
        kategorije.append({
            'tag': int(kategorija.groupdict()['tag']),
            'kat': kategorija.groupdict()['kat']
        })
    return kategorije


def polepsaj_podatke(recept: dict):
    """Funkcija sprejme slovar, ki vsebuje podatke o receptu, in te spremeni v primerno obliko (tip)."""
    recept['num_comments'] = int(recept['num_comments'].strip())
    recept['num_votes'] = int(recept['num_votes'].strip())
    recept['rating'] = (float(recept['rating'].strip()) if recept['rating'] != '0' else '')
    recept['time'] = int(recept['time'].strip())
    recept['difficulty'] = uredi_tezavnost(recept['difficulty'].strip(), recept['id'])
    datum = datetime.datetime.strptime(recept['date'].strip(), '%d.%m.%Y').date().isoformat()
    recept['date'] = datum
    recept['calories'] = (int(recept['calories']) if recept['calories'] != '' else recept['calories'])
    recept['info'] = recept['info'].strip()

    recept['sestavine'] = izloci_sestavine(recept['sestavine'])
    recept['category'] = izloci_kategorije(recept['category'])

    return recept


def izloci_gnezdene_podatke(recepti):
    kategorije, rk, sestavine = [], [], []
    videne_kategorije = set()

    def dodaj_kat(recept, kategorija):
        if kategorija['tag'] not in videne_kategorije:
            videne_kategorije.add(kategorija['tag'])
            kategorije.append(kategorija)
        rk.append({
            'recept': recept['id'],
            'kategorija': kategorija['tag']
        })

    for recept in recepti:
        for sestavina in recept.pop('sestavine'):
            sestavine.append({'recept': recept['id'], 'sestavina': sestavina})
        for kategorija in recept.pop('category'):
            dodaj_kat(recept, kategorija)

    kategorije.sort(key=lambda kat: kat['tag'])
    rk.sort(key=lambda p: (p['recept'], p['kategorija']))
    sestavine.sort(key=lambda q: (q['recept'], q['sestavina']))

    return kategorije, rk, sestavine


def preberi_podatke(i):
    """Funkcija sprejme id recepta in prebere podatke o njem s spletne strani ter jih doda v seznam urejenih slovarjev.
    Pri tem vsak slovar predstavlja en recept."""

    # Najprej spletno stran shranimo v lokalno datoteko
    url = f"https://www.chefkoch.de/rezepte/{i}"
    path = os.path.join(RECEPTI_DIR, f"recept-{i}.html")
    res = orodja.shrani_spletno_stran(url, path)

    # Preverimo, ali je shranjevanje uspelo
    if not os.path.isfile(path) or res == 404:
        return

    # Iz lokalnih (html) datotek preberemo podatke
    podatki_str = orodja.vsebina_datoteke(path)

    # Med podatki poiščemo podatke o receptu
    podatki = pridobi_podatke(podatki_str, i)

    # Podatke prevedemo v lepšo obliko (seznam slovarjev)
    lepsi_podatki = polepsaj_podatke(podatki)
    return lepsi_podatki


def id_gen(i):
    tag = TAG_START
    while tag < i + TAG_START:
        p = pridobi_id(tag)
        if p:
            yield p
        tag += 1


def main(i, redownload=True, reparse=True):
    """Funkcija izvede celoten del pridobivanja podatkov:
    1. Prenese recepte s spletne strani
    2. Lokalno html datoteko pretvori v lepšo predstavitev podatkov
    3. Podatke shrani v csv datoteko
    """


    # Najprej preberemo podatke za vsako spletno stran z receptom posebej
    recepti = []
    recepti_id = set()
    for t in id_gen(i):
        for id in t:
            if id not in recepti_id:
                recepti_id.add(id)
                novo = preberi_podatke(id)
                recepti.append(novo)
    recepti.sort(key=lambda recept: recept['id'])

    # Izločimo gnezdene podatke
    kategorije, rk, sestavine = izloci_gnezdene_podatke(recepti)

    # Podatke shranimo v json datoteke
    orodja.zapisi_json(
        recepti,
        RECEPTI_JSON
    )
    orodja.zapisi_json(kategorije, KATEGORIJE_JSON)
    orodja.zapisi_json(rk, RK_JSON)
    orodja.zapisi_json(sestavine, SESTAVINE_JSON)

    # Podatke shranimo v csv datoteke
    orodja.zapisi_csv(
        recepti,
        ['id', 'title', 'info', 'num_comments', 'num_votes', 'rating', 'time', 'difficulty', 'date', 'calories'],
        RECEPTI_CSV)
    orodja.zapisi_csv(kategorije, ['tag', 'kat'], KATEGORIJE_CSV)
    orodja.zapisi_csv(rk, ['recept', 'kategorija'], RK_CSV)
    orodja.zapisi_csv(sestavine, ['recept', 'sestavina'], SESTAVINE_CSV)



main(NUM_TAGS)