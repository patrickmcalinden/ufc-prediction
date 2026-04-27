---
slug: project-outline
title: TWISTER Project Intro
date: 2026-04-19
summary: Brief outline of the technical data ingestion and introduction into the project.
---

# The Project

Welcome to **TWISTER**, a UFC fight prediction project. I’ve been a fan of MMA for a long time, and in an effort to level up my data engineering and science skills, I decided to merge the two. This project is my sandbox—a place to learn more about the sport through the lens of data.

# The Goal 
The ultimate (and likely impossible) dream is to predict every winner with 100% accuracy. Back in reality, I’m gunning for a **back-testing accuracy of 80%** and a live-prediction rate of **over 50%**. 

To get there, I’m scraping historical martial arts variables directly from ESPN and the UFC website. I’m feeding that data into a custom weighting equation and a machine learning model to see just how close we can get to the "perfect" prediction.

Beyond the numbers, this is about professional growth. I work as an analyst, but I often find myself stuck in the world of averages and percentiles. TWISTER is the catalyst I’m using to push my horizons into heavier statistics and proper data engineering/science.

# Tech Stack Overview
* **Data Retrieval**: A suite of Python scripts utilizing `BeautifulSoup` to ingest raw stats and populate a **PostgreSQL** database.
* **Prediction Module**: A customized equation that factors in prior fight stats and ELO ratings, synchronized with **XGBoost** Gradient Tree Classifiers. Currently, I'm using a basic train/test split, but I plan to implement more robust cross-validation methods in the future.
* **Backend**: Powered by **FastAPI**. This is new for me, so while the current build is functional, I’m looking forward to refactoring it as I learn more about asynchronous Python.
* **Frontend**: Built with **Vite + React** and styled with **Tailwind CSS**.

# Acknowledgments

This project wouldn't have started without [sbalagan22](https://github.com/sbalagan22). His work on the Octagon AI scraper did the heavy lifting for the initial data collection and saved me countless hours. You can check out his project at [octagonai.app](https://www.octagonai.app/) to see how our predictions compare.

Also, a thanks to the Anthropic team 🙄. Without Claude, there wouldn't be a front end lol.

*More journals coming soon.*
