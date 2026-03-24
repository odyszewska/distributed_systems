# Voting API

A simple Doodle-style API built with FastAPI.

This application allows users to:
- create polls
- view all polls
- view a single poll
- update poll data
- delete polls
- cast votes inside polls
- view votes in a poll
- delete votes
- see poll results

The API can be tested using **Swagger UI**.


## Requirements

Install dependencies first:

    pip install fastapi uvicorn pydantic

## How to run

Start the server with:

    uvicorn vote:app --reload

## Available URLs

After starting the app, it will be available at:

- API base: `http://127.0.0.1:8000/`
- Swagger UI: `http://127.0.0.1:8000/docs`

## Data models

### Poll
A poll contains:
- `title` – poll title
- `description` – optional poll description
- `options` – list of voting options

### Vote
A vote contains:
- `voter_name` – name of the voter
- `option_id` – id of the selected option

## Endpoints

### Polls

- `POST /polls` – create a new poll
- `GET /polls` – get all polls
- `GET /polls/{poll_id}` – get one poll
- `PUT /polls/{poll_id}` – update a poll
- `DELETE /polls/{poll_id}` – delete a poll

### Votes

- `POST /polls/{poll_id}/votes` – add a vote to a poll
- `GET /polls/{poll_id}/votes` – get all votes in a poll
- `DELETE /polls/{poll_id}/votes/{vote_id}` – delete a vote

### Results

- `GET /polls/{poll_id}/results` – get voting results for a poll

## Example poll request

    POST /polls

Example body:

    {
      "title": "Best day for meeting",
      "description": "Choose the best option",
      "options": ["Monday 10:00", "Tuesday 12:00", "Wednesday 15:00"]
    }

## Example vote request

    POST /polls/0/votes

Example body:

    {
      "voter_name": "Alice",
      "option_id": 1
    }

## Example results response

    {
      "poll_id": 0,
      "title": "Best day for meeting",
      "description": "Choose the best option",
      "results": [
        {
          "option_id": 0,
          "option_text": "Monday 10:00",
          "votes": 1
        },
        {
          "option_id": 1,
          "option_text": "Tuesday 12:00",
          "votes": 2
        },
        {
          "option_id": 2,
          "option_text": "Wednesday 15:00",
          "votes": 0
        }
      ]
    }
