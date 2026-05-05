"""Seed the DB with real movies on first startup. Enriches poster_path via TMDB if key is set."""
from sqlmodel import Session, select
from ..models.db_models import Movie
from .tmdb import fetch_poster_path


FIXTURE_MOVIES = [
    Movie(id="m01", title="Inception",                          year=2010, runtime=148, rating=8.8, genres="Action,Sci-Fi,Thriller",    synopsis="A thief who steals corporate secrets through dream-sharing technology is given the inverse task of planting an idea.",     providers="Max",           hue=220, variant="halftone",  mood="mind-bending"),
    Movie(id="m02", title="Parasite",                           year=2019, runtime=132, rating=8.5, genres="Comedy,Drama,Thriller",      synopsis="Greed and class discrimination threaten the newly formed symbiotic relationship between the wealthy Park family and the destitute Kim clan.", providers="Max",           hue=120, variant="spotlight", mood="tense"),
    Movie(id="m03", title="Interstellar",                       year=2014, runtime=169, rating=8.6, genres="Adventure,Drama,Sci-Fi",     synopsis="A team of explorers travel through a wormhole in space in an attempt to ensure humanity's survival.",                     providers="Paramount+",    hue=200, variant="gradient",  mood="cerebral"),
    Movie(id="m04", title="La La Land",                         year=2016, runtime=128, rating=8.0, genres="Drama,Music,Romance",        synopsis="While navigating their careers in Los Angeles, a pianist and an actress fall in love while attempting to reconcile their aspirations with the realities of life.", providers="Netflix",       hue=280, variant="spotlight", mood="dreamy"),
    Movie(id="m05", title="The Dark Knight",                    year=2008, runtime=152, rating=9.0, genres="Action,Crime,Drama",         synopsis="When the menace known as the Joker wreaks havoc and chaos on the people of Gotham, Batman must accept one of the greatest psychological and physical tests of his ability to fight injustice.", providers="Max",           hue=210, variant="gradient",  mood="epic"),
    Movie(id="m06", title="Everything Everywhere All at Once",  year=2022, runtime=139, rating=7.8, genres="Action,Adventure,Comedy",    synopsis="A middle-aged Chinese immigrant is swept up in an insane adventure in which she alone can save existence by exploring other universes.", providers="Showtime",      hue=350, variant="bars",      mood="mind-bending"),
    Movie(id="m07", title="Her",                                year=2013, runtime=126, rating=8.0, genres="Drama,Romance,Sci-Fi",       synopsis="In a near future, a lonely writer develops an unlikely relationship with an operating system designed to meet his every need.", providers="Max",           hue=25,  variant="gradient",  mood="melancholy"),
    Movie(id="m08", title="Get Out",                            year=2017, runtime=104, rating=7.7, genres="Horror,Mystery,Thriller",    synopsis="A young African-American visits his white girlfriend's parents for the weekend, where his simmering uneasiness about their reception of him eventually reaches a boiling point.", providers="Peacock",       hue=140, variant="gradient",  mood="tense"),
    Movie(id="m09", title="Knives Out",                         year=2019, runtime=130, rating=7.9, genres="Comedy,Crime,Drama",         synopsis="A detective investigates the death of a patriarch of an eccentric, combative family.",                                      providers="Prime Video",   hue=40,  variant="halftone",  mood="witty"),
    Movie(id="m10", title="The Grand Budapest Hotel",           year=2014, runtime=99,  rating=8.1, genres="Adventure,Comedy,Crime",     synopsis="The adventures of Gustave H, a legendary concierge at a famous hotel in the fictional Republic of Zubrowka.",               providers="Max",           hue=330, variant="spotlight", mood="feel-good"),
    Movie(id="m11", title="Mad Max: Fury Road",                 year=2015, runtime=120, rating=8.1, genres="Action,Adventure,Sci-Fi",    synopsis="In a post-apocalyptic wasteland, a woman rebels against a tyrannical ruler in search for her homeland.",                     providers="Max",           hue=30,  variant="bars",      mood="fun"),
    Movie(id="m12", title="Whiplash",                           year=2014, runtime=107, rating=8.5, genres="Drama,Music",                synopsis="A promising young drummer enrolls at a cut-throat music conservatory where his dreams of greatness are mentored by an instructor who will stop at nothing to realize a student's potential.", providers="Netflix",       hue=10,  variant="gradient",  mood="tense"),
    Movie(id="m13", title="Moonlight",                          year=2016, runtime=111, rating=7.4, genres="Drama",                      synopsis="A young African-American man grapples with his identity and sexuality while experiencing the hardships of childhood, adolescence, and burgeoning adulthood.", providers="Prime Video",   hue=200, variant="spotlight", mood="melancholy"),
    Movie(id="m14", title="Spirited Away",                      year=2001, runtime=125, rating=8.6, genres="Animation,Adventure,Family", synopsis="During her family's move to the suburbs, a sullen 10-year-old girl wanders into a world ruled by gods, witches, and spirits.",  providers="Max",           hue=180, variant="gradient",  mood="dreamy"),
    Movie(id="m15", title="Portrait of a Lady on Fire",         year=2019, runtime=122, rating=8.1, genres="Drama,History,Romance",      synopsis="On an isolated island in Brittany at the end of the eighteenth century, a female painter is obliged to paint a wedding portrait of a young woman.", providers="Mubi",          hue=20,  variant="stripes",   mood="cerebral"),
    Movie(id="m16", title="Hereditary",                         year=2018, runtime=127, rating=7.3, genres="Drama,Horror,Mystery",       synopsis="A grieving family is haunted by tragic and disturbing occurrences after the death of their secretive grandmother.",            providers="Max",           hue=55,  variant="halftone",  mood="tense"),
]


def seed_movies(db: Session) -> None:
    for movie in FIXTURE_MOVIES:
        if not db.get(Movie, movie.id):
            db.add(movie)
    db.commit()

    # Fill in any missing poster paths via TMDB (only if API key configured)
    movies_missing_poster = db.exec(
        select(Movie).where(Movie.poster_path == "")
    ).all()
    if movies_missing_poster:
        for m in movies_missing_poster:
            path = fetch_poster_path(m.title, m.year)
            if path:
                m.poster_path = path
        db.commit()
