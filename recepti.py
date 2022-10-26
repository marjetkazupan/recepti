import re, os, orodja


STEVILO_STRANI = 30
RECEPTI_DIR = 'recepti_spletne-strani'
RECEPTI_JSON = 'recepti.json'
RECEPTI_CSV = "recepti.csv"



def poisci_recepte(vzorec_bloka, page_content):
    """Funkcija poišče posamezne recepte, ki se nahajajo na spletni strani in vrne seznam receptov."""
    vzorec = re.compile(vzorec_bloka, flags=re.DOTALL)
    return re.findall(vzorec, page_content)


def izlusci_podatke(niz):
    """Funkcija sprejme niz, ki predstavlja recept, in vrne slovar podatkov o receptu."""
    rx = re.compile(r'id="recipe-(?P<id>.*?)" '
                    r'data-vars-recipe-title="(?P<title>.*?)"'
                    r'.*?data-vars-num-votes="(?P<num_votes>\d*?)" '
                    r'data-vars-rating="(?P<rating>.*?)" data-vars-has-video="(\d)"'
                    r'.*?<a href="(?P<url>.*?)"'
                    r'.*?class="ds-recipe-info__text">(?P<time>\d*?) Min.<'
                    r'.*?class="ds-recipe-info__text">(?P<difficulty>.*?)<',
                    re.DOTALL)
    data = re.search(rx, niz)
    sl = data.groupdict()

    # Če ima recept objavljen opis, dodamo še tega
    opis_rx = re.compile(r'description ds-text-caption ds-trunc ds-trunc-2">(?P<info>.*?)</div> <!----> <!----> <!---->', re.DOTALL)
    desc = re.search(opis_rx, niz)
    if desc is not None:
        sl['info'] = desc.group('info')
    else:
        sl['info'] = 'Unbekannt'
    return sl


def uredi_tezavnost(t: str, id):
    if t == 'simpel':
        return 0
    if t == 'normal':
        return 1
    if t == 'pfiffig':
        return 2
    else:
        print(f'Prišlo je do napake pri težavnosti recepta {id}. Vnešena vrednost: {t}')
        return 'Unbekannt'


def polepsaj_podatke(recept: dict):
    """Funkcija sprejme slovar, ki vsebuje podatke o receptu, in te spremeni v primerno obliko (tip)."""
    recept['id'] = int(recept['id'])
    recept['num_votes'] = int(recept['num_votes'])
    recept['rating'] = float(recept['rating'])
    recept['time'] = int(recept['time'])
    recept['difficulty'] = uredi_tezavnost(recept['difficulty'], recept['id'])
    recept['info'] = recept['info'].strip()
    return recept


def preberi_podatke(i):
    """Funkcija prebere podatke s spletne strani in jih shrani v seznam urejenih slovarjev.
    Pri tem vsak slovaer predstavlja en recept."""

    # Najprej spletno stran shranimo v lokalno datoteko
    url = f"https://www.chefkoch.de/rs/s{i}/Rezepte.html"
    path = os.path.join(RECEPTI_DIR, f"stran-{i}.html")
    orodja.shrani_spletno_stran(url, path)

    # Preverimo, ali je shranjevanje uspelo
    if not os.path.isfile(path):
        return

    # Iz lokalnih (html) datotek preberemo podatke
    podatki_str = orodja.vsebina_datoteke(path)

    # Med podatki poiščemo bloke z recepti
    vzorec_bloka = r'<div data-vars-position="\d*" data-vars-tracking-(.*?)<\/a>'
    podatki = poisci_recepte(vzorec_bloka, podatki_str)

    # Podatke prevedemo v lepšo obliko (seznam slovarjev)
    lepsi_podatki = [polepsaj_podatke(izlusci_podatke(recept)) for recept in podatki]
    return lepsi_podatki


def main(i, redownload=True, reparse=True):
    """Funkcija izvede celoten del pridobivanja podatkov:
    1. Prenese recepte s spletne strani
    2. Lokalno html datoteko pretvori v lepšo predstavitev podatkov
    3. Podatke shrani v csv datoteko
    """

    # Najprej preberemo podatke za vsako spletno stran posebej
    recepti = []
    for j in range(i):
        p = preberi_podatke(j)
        if p:
            recepti += p


    # Podatke shranimo v json datoteko
    orodja.zapisi_json(
        recepti,
        RECEPTI_JSON
    )

    # Podatke shranimo v csv datoteko
    orodja.zapisi_csv(
        recepti,
        ['id', 'title', 'num_votes', 'rating', 'url', 'time', 'difficulty', 'info'],
        RECEPTI_CSV)



main(STEVILO_STRANI)