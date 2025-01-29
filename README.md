# LLMeme

## Description

LLMeme is a tool that suggests memes to users based on ideas and text descriptions. It was was made as a homework submission to the LLM SDLC course carried out in Jan 2025 - [link](https://maven.com/hugo-stefan/building-llm-apps-ds-and-swe-from-first-principles)

## Contributions

You're welcome to contribute to this project through opening an issue or a pull request.

## Acknowledgements

- Hugo Bowne-Anderson and Stefan Krawczyk for the instruction and much of the template code.
- [meme-cap](https://github.com/eujhwang/meme-cap/tree/main) - a dataset of LLM captioned memes from r/meme - authored by `EunJeong Hwang and Vered Shwartz`.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Journal

### Initial Scope
- [ ] Prototype prompts using a variety of LLMs and an open dataset of memes - WIP
- [ ] Deploy a streamlit demo using a cloud service called maven
- [ ] Evaluate the performance of the prompts using a test database, human annotation, stretch LLM as a judge
- [ ] Create tests for the prompts (using pytest)
- [ ] Incorporate CI/CD using github actions
- [ ] Experiment with semantic search and if need be vector databases
- [ ] Create an agentic system that can generate memes in discord

### First Sprint
All that got too complicated and in the way of user feedback - so simplified to the following simple call and app in GradIO:

![initial-flow](./assets/llmeme-concept.png)