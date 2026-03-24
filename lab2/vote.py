from fastapi import Body, FastAPI, status
from enum import Enum
from typing import Union
from pydantic import BaseModel
from fastapi.responses import JSONResponse

app=FastAPI(title="Voting API" )

polls = {}
poll_counter = 0
vote_counter = 0

class Poll(BaseModel):
    title: str
    description: Union[str, None] = None
    options: list[str]

class PollUpdate(BaseModel):
    title: Union[str, None] = None
    description: Union[str, None] = None
    options: Union[list[str], None] = None

class Vote(BaseModel):
    voter_name: str
    option_id: int



@app.post("/polls")
async def create_poll(poll: Poll):
    global poll_counter

    if len(poll.options) < 2:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message": "A poll must have at least 2 options."},
        )
    
    options_list = []
    idx = 0
    for option_text in poll.options:
        options_list.append({
            "id": idx,
            "text": option_text})
        idx += 1

    new_poll = {
        "id": poll_counter,
        "title": poll.title,
        "description": poll.description,
        "options": options_list,
        "votes": []
    }

    polls[poll_counter] = new_poll
    poll_counter += 1

    return new_poll

@app.get("/polls")
async def get_polls():
    return list(polls.values())

@app.get("/polls/{poll_id}")
async def get_poll(poll_id: int):
    if poll_id not in polls:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"message": "Poll not found."},
        )
    return polls[poll_id]

@app.put("/polls/{poll_id}")
async def update_poll(poll_id: int, poll_update: PollUpdate):
    if poll_id not in polls:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"message": "Poll not found."},
        )

    poll = polls[poll_id]
    if poll_update.title is not None:
        poll["title"] = poll_update.title
    if poll_update.description is not None:
        poll["description"] = poll_update.description
    if poll_update.options is not None:
        if len(poll_update.options) < 2:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"message": "A poll must have at least 2 options."},
            )
        options_list = []
        idx = 0
        for option_text in poll_update.options:
            options_list.append({
                "id": idx,
                "text": option_text})
            idx += 1
            
        poll["options"] = options_list
        poll["votes"] = []


    polls[poll_id] = poll
    return poll

@app.delete("/polls/{poll_id}")
async def delete_poll(poll_id: int):
    if poll_id not in polls:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"message": "Poll not found."},
        )

    del polls[poll_id]
    return JSONResponse(status_code=status.HTTP_204_NO_CONTENT, content={"message": "Poll deleted successfully."})

@app.post("/polls/{poll_id}/votes")
async def create_vote(poll_id: int, vote: Vote):
    global vote_counter

    if poll_id not in polls:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"message": "Poll not found."},
        )

    found = False

    for option in polls[poll_id]["options"]:
        if option["id"] == vote.option_id:
            found = True

    if not found:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"message": "Option not found."},
        )
    
    new_vote = {
        "id": vote_counter,
        "voter_name": vote.voter_name,
        "option_id": vote.option_id
    }
    polls[poll_id]["votes"].append(new_vote)
    vote_counter += 1

    return new_vote

@app.get("/polls/{poll_id}/votes")
async def get_votes(poll_id: int):
    if poll_id not in polls:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"message": "Poll not found."},
        )
    return polls[poll_id]["votes"]

    
@app.delete("/polls/{poll_id}/votes/{vote_id}")
async def delete_vote(poll_id: int, vote_id: int):
    if poll_id not in polls:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"message": "Poll not found."},
        )

    vote_found = False
    for vote in polls[poll_id]["votes"]:
        if vote["id"] == vote_id:
            vote_found = True

    if not vote_found:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"message": "Vote not found."},
        )
    
    polls[poll_id]["votes"] = [vote for vote in polls[poll_id]["votes"] if vote["id"] != vote_id]
    return JSONResponse(status_code=status.HTTP_204_NO_CONTENT, content={"message": "Vote deleted successfully."})
    
    

@app.get("/polls/{poll_id}/results")
async def get_results(poll_id: int):
    if poll_id not in polls:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"message": "Poll not found."},
        )

    poll = polls[poll_id]
    results = []
    for option in poll["options"]:
        vote_count = 0
        
        for vote in poll["votes"]:
            if vote["option_id"] == option["id"]:
                vote_count += 1
        
        results.append({
            "option_id": option["id"],
            "option_text": option["text"],
            "votes": vote_count
        })

    return {
        "poll_id": poll_id,
        "title": poll["title"],
        "description": poll["description"],
        "results": results
    }
