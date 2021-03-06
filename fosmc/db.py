import datetime
import os

from slugify import slugify as _slugify
import yaml


def slugify(value):
    if isinstance(value, unicode):
        return _slugify(value)
    else:
        return _slugify(value.decode('utf8'))


def load_data(path):
    db = dict(
        city={},
        dj={},
        event={},
        genre={},
        recording={},
    )
    # Load data in the order of most authoritative to least authoritative
    # (regarding spelling of names and mapping of names to slugs).
    load_cities(path, db)
    load_genres(path, db)
    load_djs(path, db)
    load_events(path, db)
    load_recordings(path, db)
    denormalize(db)
    return db


def load_cities(path, db):
    with open(os.path.join(path, 'cities.yaml')) as f:
        for city in yaml.load_all(f):
            _populate_slug_and_name(city)
            _store_replacement(db['city'], city)
            db['city'][city['slug']] = city

def load_genres(path, db):
    with open(os.path.join(path, 'genres.yaml')) as f:
        for genre in yaml.load_all(f):
            _populate_slug_and_name(genre)
            _store_replacement(db['genre'], genre)
            db['genre'][genre['slug']] = genre


def load_djs(path, db):
    with open(os.path.join(path, 'djs.yaml')) as f:
        for dj in yaml.load_all(f):
            _populate_slug_and_name(dj)
            _store_replacement(db['dj'], dj)
            db['dj'][dj['slug']] = dj
            if 'city' in dj:
                city = dj['city']
                cityslug = slugify(city)
                if cityslug not in db['city']:
                    db['city'][cityslug] = dict(
                        name=city,
                        slug=cityslug,
                        lint_created_by_dj=dj['slug'],
                    )
                dj['city'] = cityslug
                city_djs = db['city'][cityslug].setdefault('djs', [])
                city_djs.append(dj['slug'])
            # Normalize 'genre' to 'genres'.
            genres = dj.setdefault('genres', [])
            if 'genre' in dj:
                genres.append(dj.pop('genre'))
            genreslugs = []
            for genre in genres:
                genreslug = slugify(genre)
                if genreslug not in db['genre']:
                    db['genre'][genreslug] = dict(
                        name=genre,
                        slug=genreslug,
                        lint_created_by_dj=dj['slug'],
                    )
                genreslugs.append(genreslug)
                genredjs = db['genre'][genreslug].setdefault('djs', [])
                genredjs.append(dj['slug'])
            dj['genres'] = genreslugs


def load_events(path, db):
    with open(os.path.join(path, 'events.yaml')) as f:
        for event in yaml.load_all(f):
            if 'slug' not in event:
                event['slug'] = slugify(event['name'])
                date = event.get('date', None)
                if date:
                    event['slug'] += '-'
                    if isinstance(date, datetime.date):
                        event['slug'] += date.strftime('%Y-%m-%d')
                    else:
                        event['slug'] += str(date)
            _store_replacement(db['event'], event)
            db['event'][event['slug']] = event
            if 'city' in event:
                city = event['city']
                cityslug = slugify(city)
                if cityslug not in db['city']:
                    db['city'][cityslug] = dict(
                        name=city,
                        slug=cityslug,
                        lint_created_by_event=event['slug'],
                    )
                event['city'] = cityslug
                city_events = db['city'][cityslug].setdefault('events', [])
                city_events.append(event['slug'])


def load_recordings(path, db):
    with open(os.path.join(path, 'recordings.yaml')) as f:
        mp3_urls = set()  # Keep track of MP3 urls to find duplicates.
        for recording in yaml.load_all(f):
            recording.setdefault('name', 'Live recording')
            recording.setdefault('date', None)
            # Mark missing MP3s as lint.
            mp3_url = recording.get('mp3')
            mp3high_url = recording.get('mp3high')
            if not mp3_url:
                recording['lint_mp3_missing'] = True
            elif mp3_url != 'auto':
                if mp3_url in mp3_urls:
                    recording['lint_mp3_duplicate'] = True
                mp3_urls.add(mp3_url)
            if mp3high_url != 'auto':
                if mp3high_url in mp3_urls:
                    recording['lint_mp3_duplicate'] = True
            # Convert single DJ to list of one DJ.
            djs = recording.setdefault('djs', [])
            if 'dj' in recording:
                djs.append(recording.pop('dj'))
            # Generate slug if not present.
            if 'slug' not in recording:
                slugs = []
                if 'event' in recording:
                    slugs.append(slugify(recording['event']))
                for dj in djs:
                    slugs.append(slugify(dj))
                slugs.append(slugify(recording['name']))
                if recording['date']:
                    if isinstance(recording['date'], datetime.date):
                        slugs.append(recording['date'].strftime('%Y-%m-%d'))
                    else:
                        slugs.append(str(recording['date']))
                recording['slug'] = '_'.join(slugs)
            _store_replacement(db['recording'], recording)
            db['recording'][recording['slug']] = recording
            # Auto-create other objects based on information present.
            # Normalize references to other objects to slugs.
            for dj in djs:
                djslug = slugify(dj)
                if djslug not in db['dj']:
                    db['dj'][djslug] = dict(
                        name=dj,
                        slug=djslug,
                        lint_created_by_recording=recording['slug'],
                    )
                dj_recordings = db['dj'][djslug].setdefault('recordings', [])
                dj_recordings.append(recording['slug'])
            recording['djs'] = [slugify(dj) for dj in recording['djs']]
            if 'city' in recording:
                city = recording['city']
                cityslug = slugify(city)
                if cityslug not in db['city']:
                    db['city'][cityslug] = dict(
                        name=city,
                        slug=cityslug,
                        lint_created_by_recording=recording['slug'],
                    )
                recording['city'] = cityslug
                city_recordings = db['city'][cityslug].setdefault('recordings', [])
                city_recordings.append(recording['slug'])
            if 'event' in recording:
                event = recording['event']
                eventslug = slugify(event)
                if eventslug not in db['event']:
                    db['event'][eventslug] = dict(
                        name=event,
                        slug=eventslug,
                        lint_created_by_recording=recording['slug'],
                    )
                recording['event'] = eventslug
                event_recordings = db['event'][eventslug].setdefault('recordings', [])
                event_recordings.append(recording['slug'])
            # Normalize 'genre' to 'genres'.
            genres = recording.setdefault('genres', [])
            if 'genre' in recording:
                genres.append(recording.pop('genre'))
            genreslugs = []
            for genre in genres:
                genreslug = slugify(genre)
                if genreslug not in db['genre']:
                    db['genre'][genreslug] = dict(
                        name=genre,
                        slug=genreslug,
                        lint_created_by_recording=recording['slug'],
                    )
                genreslugs.append(genreslug)
                genrerecordings = db['genre'][genreslug].setdefault('recordings', [])
                genrerecordings.append(recording['slug'])
            recording['genres'] = genreslugs


def denormalize(db):
    # Recording genres contribute to DJ genres.
    for recording in db['recording'].itervalues():
        for djslug in recording['djs']:
            dj = db['dj'][djslug]
            for genreslug in recording.get('genres', []):
                djgenres = dj.setdefault('genres', [])
                if genreslug not in djgenres:
                    djgenres.append(genreslug)
    # DJ cities contribute DJ's recordings to city's recordings.
    for dj in db['dj'].itervalues():
        cityslug = dj.get('city', None)
        if cityslug is not None:
            for recordingslug in dj.get('recordings', []):
                cityrecordings = db['city'][cityslug].setdefault('recordings', [])
                if recordingslug not in cityrecordings:
                    cityrecordings.append(recordingslug)
    # Event cities contribute event's recordings to city's recordings.
    for event in db['event'].itervalues():
        cityslug = event.get('city', None)
        if cityslug is not None:
            for recordingslug in event.get('recordings', []):
                cityrecordings = db['city'][cityslug].setdefault('recordings', [])
                if recordingslug not in cityrecordings:
                    cityrecordings.append(recordingslug)
    # Link DJs aliases.
    for dj in db['dj'].values():
        for alias in dj.get('aliases', []):
            aliasslug = slugify(alias)
            if aliasslug not in db['dj']:
                db['dj'][aliasslug] = dict(
                    slug=aliasslug,
                    name=alias,
                    alias_for=dj['slug'],
                )
            else:
                dj['lint_cannot_clone_alias_' + aliasslug] = True
    # Event dates populate recording dates when not present on recordings.
    for event in db['event'].values():
        if not event.get('date'):
            # Event itself doesn't have a date.
            continue
        for recordingslug in event.get('recordings', []):
            if not db['recording'][recordingslug].get('date'):
                db['recording'][recordingslug]['date'] = event['date']
    # Recording events are used to populate DJs' events, and events' DJs.
    for recording in db['recording'].values():
        eventslug = recording.get('event')
        if eventslug and recording['djs']:
            eventdjs = db['event'][eventslug].setdefault('djs', [])
            for djslug in recording['djs']:
                djevents = db['dj'][djslug].setdefault('events', [])
                if eventslug not in djevents:
                    djevents.append(eventslug)
                if djslug not in eventdjs:
                    eventdjs.append(djslug)


def _populate_slug_and_name(obj):
    if 'slug' not in obj:
        # Generate slug from name if slug not present.
        obj['slug'] = slugify(obj['name'])
    elif 'name' not in obj:
        # Name not given, only slug; copy slug into name and tag for lint.
        obj['name'] = obj['slug']
        obj['lint_name_from_slug'] = True


def _store_replacement(obj_dict, obj):
    if obj['slug'] in obj_dict:
        obj['lint_replaces'] = obj_dict[obj['slug']]  # Tag for lint.
