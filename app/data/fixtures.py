"""Seed the DB with fixture movies on first startup."""
from sqlmodel import Session, select
from ..models.db_models import Movie


FIXTURE_MOVIES = [
    Movie(id="m01", title="The Quiet Engine",     year=2023, runtime=118, rating=8.1, genres="Drama,Mystery",     synopsis="A retired engineer in rural Norway returns to a derelict factory to confront a sound only he can hear.", providers="Netflix",  hue=28,  variant="gradient",  mood="mind-bending"),
    Movie(id="m02", title="Velvet Static",        year=2021, runtime=96,  rating=7.4, genres="Comedy,Romance",    synopsis="Two radio hosts in 1990s Bucharest pretend to be in love on air, and start to mean it.",              providers="HBO Max",  hue=350, variant="spotlight", mood="feel-good"),
    Movie(id="m03", title="North of Memory",      year=2024, runtime=134, rating=8.4, genres="Drama,Sci-Fi",      synopsis="An archivist discovers a rented apartment that remembers every previous tenant, all at once.",          providers="HBO Max",  hue=220, variant="halftone",  mood="cerebral"),
    Movie(id="m04", title="Bring The House Down", year=2022, runtime=102, rating=7.0, genres="Comedy,Action",     synopsis="A failing demolition crew accepts a job with complicated paperwork.",                                   providers="Netflix",  hue=18,  variant="bars",      mood="fun"),
    Movie(id="m05", title="Ash Garden",           year=2020, runtime=124, rating=8.6, genres="Drama,Historical",  synopsis="A Japanese gardener tends a memorial in post-war Hiroshima for forty years and one season.",             providers="Mubi",     hue=40,  variant="gradient",  mood="meditative"),
    Movie(id="m06", title="The Last Telephone",   year=2019, runtime=88,  rating=7.2, genres="Thriller,Mystery",  synopsis="A booth on a Welsh cliff begins to ring. The number is yours, twelve years from now.",                   providers="Disney+",  hue=280, variant="stripes",   mood="tense"),
    Movie(id="m07", title="Fluorescence",         year=2024, runtime=109, rating=7.8, genres="Sci-Fi,Romance",    synopsis="Two strangers meet at a bioluminescence research lab on the night the lights go wrong.",                  providers="Netflix",  hue=180, variant="spotlight", mood="dreamy"),
    Movie(id="m08", title="Catch the Moonshade",  year=2018, runtime=145, rating=8.0, genres="Adventure,Family",  synopsis="A Romanian girl, a one-eyed dog, and a moon that won't set on time.",                                   providers="Disney+",  hue=60,  variant="gradient",  mood="feel-good"),
    Movie(id="m09", title="Concrete Lullaby",     year=2023, runtime=99,  rating=7.6, genres="Drama,Music",       synopsis="A noise musician inherits her late mother's tape collection, and starts playing it backward.",            providers="Mubi",     hue=320, variant="halftone",  mood="melancholy"),
    Movie(id="m10", title="Hotel Pacific",        year=2025, runtime=116, rating=7.9, genres="Mystery,Drama",     synopsis="A night manager suspects Room 312 is not in the same building as the rest of the hotel.",                 providers="HBO Max",  hue=200, variant="spotlight", mood="noir"),
    Movie(id="m11", title="How to Lose a War",    year=2017, runtime=128, rating=8.2, genres="Comedy,Drama",      synopsis="A retired general accidentally writes a self-help bestseller and has to live up to it.",                   providers="Netflix",  hue=100, variant="bars",      mood="witty"),
    Movie(id="m12", title="Glassland",            year=2022, runtime=107, rating=7.5, genres="Drama,Thriller",    synopsis="A glassblower in a closing factory takes the night shift and finds someone else has already started it.", providers="Mubi",     hue=240, variant="gradient",  mood="tense"),
    Movie(id="m13", title="Soft Crash",           year=2024, runtime=94,  rating=7.1, genres="Romance,Comedy",    synopsis="Two strangers crash electric scooters into each other every Tuesday for six months.",                     providers="Netflix",  hue=8,   variant="spotlight", mood="cozy"),
    Movie(id="m14", title="The Inheritor",        year=2021, runtime=138, rating=8.3, genres="Drama,Historical",  synopsis="An estate, a brother, a sister, and a forest that keeps moving the property line.",                      providers="HBO Max",  hue=50,  variant="gradient",  mood="epic"),
    Movie(id="m15", title="Spinwave",             year=2023, runtime=91,  rating=6.9, genres="Action,Sci-Fi",     synopsis="A skateboarder bends time three seconds at a time. It is enough, and it is not.",                        providers="Disney+",  hue=295, variant="halftone",  mood="fun"),
    Movie(id="m16", title="Coastline Etiquette",  year=2020, runtime=86,  rating=7.3, genres="Comedy,Romance",    synopsis="A finishing school relocates to an oil rig. Manners persist.",                                          providers="Mubi",     hue=165, variant="stripes",   mood="feel-good"),
]


def seed_movies(db: Session) -> None:
    existing = db.exec(select(Movie)).first()
    if existing:
        return  # Already seeded
    for movie in FIXTURE_MOVIES:
        db.add(movie)
    db.commit()
