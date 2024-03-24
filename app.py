from flask import Flask, request, jsonify, redirect
from flask_sqlalchemy import SQLAlchemy
from models import db, Actor, Movie, MovieActor
import os
from dotenv import load_dotenv
from functools import wraps
from authlib.integrations.flask_client import OAuth
from authlib.jose import jwt
import urllib.parse
from auth import *


# Load environment variables from .env file
load_dotenv()

# Use DATABASE_URL from the .env file
app = Flask(__name__)
app.config['ENV'] = 'production'
database_uri = os.getenv('DATABASE_URL', 'sqlite:///fallback.db')

if database_uri.startswith("postgres://"):
    database_uri = database_uri.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['DEBUG'] = False

db.init_app(app)

# Create tables in db if they don't exist
with app.app_context():
    db.create_all()  # Optionally create tables if they don't exist



# ENDPOINTS

# Endpoint to redirect to OAuth URL
@app.route('/login')
def login():
    auth0_url = 'https://dev-ri7inc1t70j00a7b.uk.auth0.com/authorize?audience=auth&response_type=token&client_id=Qub03BeIgyxAunuP57OmVazbgGmbAux3&redirect_uri=http://127.0.0.1:5000/login-result'
    return redirect(auth0_url)


 

@app.route('/actors', methods=['GET'])
@requires_auth('view:actors')
def get_actors(payload):
    
    if 'view:actors' not in payload['permissions']:
        return jsonify({'error': 'Forbidden', 'message': 'You do not have permission to view actors'}), 403
    
    actors = Actor.query.all()

     # Check if there are no actors
    if not actors:
        return jsonify({
            'success': False,
            'error': 404,
            'message': 'No Actors found.'
        }), 404
    
    actor_list = []
    for actor in actors:
        actor_data = {
            'id': actor.id,
            'name': actor.name,
            'age': actor.age,
            'gender': actor.gender,
            'movies': [{'movie_id': movie.id, 'title': movie.title, 'release_date': movie.release_date.isoformat()} for movie in actor.movies]
        }
        actor_list.append(actor_data)
    return jsonify(actor_list), 200

@app.route('/movies', methods=['GET'])
@requires_auth('view:movies')
def get_movies(payload):
    movies = Movie.query.all()

    # Check if there are no movies
    if not movies:
        return jsonify({
            'success': False,
            'error': 404,
            'message': 'No Movies found.'
        }), 404
    
    movie_list = []
    for movie in movies:
        movie_data = {
            'id': movie.id,
            'title': movie.title,
            'release_date': movie.release_date.isoformat(),
            'actors': [{'actor_id': actor.id, 'name': actor.name, 'age': actor.age, 'gender': actor.gender} for actor in movie.actors]
        }
        movie_list.append(movie_data)
    return jsonify(movie_list), 200

@app.route('/actors/<int:id>', methods=['GET'])
@requires_auth('view:actors')
def get_actor_by_id(payload, id):
    actor = Actor.query.get_or_404(id)

    # Check if there are no Actors
    if not actor:
        return jsonify({
            'success': False,
            'error': 404,
            'message': 'No Actor found.'
        }), 404
    
    actor_data = {
        'id': actor.id,
        'name': actor.name,
        'age': actor.age,
        'gender': actor.gender,
        'movies': [{'movie_id': movie.id, 'title': movie.title, 'release_date': movie.release_date.isoformat()} for movie in actor.movies]
    }
    return jsonify(actor_data), 200

@app.route('/movies/<int:id>', methods=['GET'])
@requires_auth('view:movies')
def get_movie_by_id(payload, id):
    movie = Movie.query.get_or_404(id)

    # Check if there are no Movies
    if not movie:
        return jsonify({
            'success': False,
            'error': 404,
            'message': 'No Movie found.'
        }), 404
    
    movie_data = {
        'id': movie.id,
        'title': movie.title,
        'release_date': movie.release_date.isoformat(),
        'actors': [{'actor_id': actor.id, 'name': actor.name, 'age': actor.age, 'gender': actor.gender} for actor in movie.actors]
    }
    return jsonify(movie_data), 200

@app.route('/actors/<int:actor_id>', methods=['PATCH'])
@requires_auth('modify:actors')
def update_actor_and_movies(payload, actor_id):
    actor = Actor.query.get_or_404(actor_id)

        # Check if there are no Actors
    if not actor:
        return jsonify({
            'success': False,
            'error': 404,
            'message': 'No Actor found.'
        }), 404
    
    data = request.json

    # Update actor's basic information
    actor.name = data.get('name', actor.name)
    actor.age = data.get('age', actor.age)
    actor.gender = data.get('gender', actor.gender)
    
    # Update actor's movies
    if 'movie_ids' in data:
        # Clear the current movie associations
        actor.movies = []
        # Associate new movies based on provided IDs
        for movie_id in data['movie_ids']:
            movie = Movie.query.get(movie_id)
            if movie:
                actor.movies.append(movie)
    
    db.session.commit()
    return jsonify({'message': 'Actor and their movies updated successfully'}), 200


@app.route('/movies/<int:movie_id>', methods=['PATCH'])
@requires_auth('modify:movies')
def update_movie_and_actors(payload, movie_id):
    movie = Movie.query.get_or_404(movie_id)

    # Check if there are no Movies
    if not movie:
        return jsonify({
            'success': False,
            'error': 404,
            'message': 'No Movie found.'
        }), 404

    data = request.json

    # Update movie's basic information
    movie.title = data.get('title', movie.title)
    movie.release_date = data.get('release_date', movie.release_date)
    
    # Update movie's actors
    if 'actor_ids' in data:
        # Clear the current actor associations
        movie.actors = []
        # Associate new actors based on provided IDs
        for actor_id in data['actor_ids']:
            actor = Actor.query.get(actor_id)
            if actor:
                movie.actors.append(actor)
    
    db.session.commit()
    return jsonify({'message': 'Movie and its actors updated successfully'}), 200


@app.route('/actors/<int:id>', methods=['DELETE'])
@requires_auth('delete:actors')
def delete_actor_by_id(payload, id):
    actor = Actor.query.get_or_404(id)

    # Manually delete associations in MovieActor for this actor
    MovieActor.query.filter_by(actor_id=id).delete()

    db.session.delete(actor)
    db.session.commit()
    return jsonify({'message': 'Actor deleted successfully'}), 200

@app.route('/movies/<int:id>', methods=['DELETE'])
@requires_auth('delete:movies')
def delete_movie_by_id(payload, id):
    movie = Movie.query.get_or_404(id)

    # Manually delete associations in MovieActor for this movie
    MovieActor.query.filter_by(movie_id=id).delete()

    db.session.delete(movie)
    db.session.commit()
    return jsonify({'message': 'Movie deleted successfully'}), 200

@app.route('/actors', methods=['POST'])
@requires_auth('add:actors')
def create_actor_and_assign_to_movie(payload):
    data = request.json
    new_actor = Actor(name=data['name'], age=data['age'], gender=data['gender'])
    db.session.add(new_actor)
    db.session.commit()

    for movie_id in data.get('movie_ids', []):
        movie = Movie.query.get(movie_id)
        if movie:
            movie.actors.append(new_actor)
    db.session.commit()

    return jsonify({'message': 'Actor created and assigned to movies successfully'}), 201


@app.route('/movies', methods=['POST'])
@requires_auth('add:movies')
def create_movie_and_assign_actors(payload):
    data = request.json
    new_movie = Movie(title=data['title'], release_date=data['release_date'])
    db.session.add(new_movie)
    db.session.commit()

    for actor_id in data.get('actor_ids', []):
        actor = Actor.query.get(actor_id)
        if actor:
            new_movie.actors.append(actor)
    db.session.commit()

    return jsonify({'message': 'Movie created and actors assigned successfully'}), 201


#Error Handling
@app.errorhandler(403)
def forbidden_error(error):
    return jsonify({'error': 'Forbidden', 'message': 'You do not have permission to access this resource'}), 403

@app.errorhandler(404)
def not_found_error(error):
    return jsonify({'error': 'Not Found', 'message': 'The requested resource was not found'}), 404

@app.errorhandler(400)
def bad_request_error(error):
    return jsonify({'error': 'Bad Request', 'message': 'The server could not understand the request due to invalid syntax'}), 400

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal Server Error', 'message': 'The server encountered an unexpected condition that prevented it from fulfilling the request'}), 500


if __name__ == '__main__':
    app.run()
