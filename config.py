from datetime import datetime


current_date_pattern = datetime.now().strftime("%Y/%m/%d")

link_dikt = {
    'polskie_radio': {
        'url': 'https://www.polskieradio.pl/protesty-w-warszawie/tag170813',
        'patterns': ['Artykul', 'artykul']
    },
    'um.warszawa.pl': {
        'url': 'https://um.warszawa.pl/aktualnosci-warszawa',
        'patterns': ['/-/']
    },
    'warszawa-diaspora': {
        'url': 'https://warszawa-diaspora.pl/',
        'patterns': [current_date_pattern]
    }
}