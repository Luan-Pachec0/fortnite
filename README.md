# 🎮 Fortnite Tracker API
Web scraping do fortnite tracker para pegar estatistica de jogadores. Projeto feito para mim e meus amigos.

Uma API de web scraping avançada para extrair **TODAS** as estatísticas vitais do Fortnite (Overview, Ranks, Matches recentes, estatísticas por modo) burlando ativamente as defesas do Cloudflare do site _Fortnite Tracker_.

## 🚀 Como Funciona
O sistema utiliza **FastAPI** para gerenciar as rotas e **Playwright + Stealth Plugin** no backend. O script foi desenhado para **isolamento perfeito**: cada requisição abre uma aba Chromium virgem e isolada, extrai os dados brutos, processa dezenas de informações complexas do DOM e encerra o navegador.

Isso significa que você pode fazer dezenas de chamadas sem que as sessões vazem, e caso o site apresente o famoso desafio _Turnstile ("Verify you are human")_, uma janela é exibida permitindo que o usuário resolva manualmente com um tempo de espera de até 5 minutos!

## ⚙️ Instalação e Execução

### 1. Preparar Ambiente
Certifique-se de que o Python 3.10+ está instalado. No terminal:
```bash
# Cria e ativa o ambiente virtual (Windows)
python -m venv venv
.\venv\Scripts\Activate.ps1

# Instalar as dependências
pip install -r requirements.txt

# Inicializar os binários do Playwright
playwright install chromium
```

### 2. Rodar o Servidor
Com o ambiente ativado, inicie o Uvicorn na raiz do projeto:
```bash
python app.py
```
O servidor será exposto em `http://localhost:8000`.

---

## 🔗 Endpoints e Como Usar

A API expõe o seguinte endpoint GET:
`/api/v1/fortnite/stats?username=<NOME_DO_JOGADOR>`

Basta abrir o seu navegador enquanto o servidor roda e testar (os nomes já estão codificados em URL %20 para os espaços):
- **034 Moreira**: [http://localhost:8000/api/v1/fortnite/stats?username=034%20Moreira](http://localhost:8000/api/v1/fortnite/stats?username=034%20Moreira)
- **Aloisio8606**: [http://localhost:8000/api/v1/fortnite/stats?username=Aloisio8606](http://localhost:8000/api/v1/fortnite/stats?username=Aloisio8606)
- **Bicho_solto_007**: [http://localhost:8000/api/v1/fortnite/stats?username=Bicho_solto_007](http://localhost:8000/api/v1/fortnite/stats?username=Bicho_solto_007)
- **Bonnie_Clydee**: [http://localhost:8000/api/v1/fortnite/stats?username=Bonnie_Clydee](http://localhost:8000/api/v1/fortnite/stats?username=Bonnie_Clydee)
- **LUAanZeRaaaa**: [http://localhost:8000/api/v1/fortnite/stats?username=LUAanZeRaaaa](http://localhost:8000/api/v1/fortnite/stats?username=LUAanZeRaaaa)

## 📁 Estrutura de Retorno (JSON Mapeado)
A API retorna os seguintes blocos de dados completos:
- `overview`: Total de horas jogadas e nível do passe.
- `estatisticas_gerais`: Lifetime stats (Vitórias gerais, K/D, Kills, Porcentagem, Partidas).
- `estatisticas_periodo`: Array contendo dados separados para `Last 7 Days` e `Last 30 Days`.
- `estatisticas_por_modo`: Array contendo metas exclusivas de cada fila (`SOLO`, `DUOS`, `TRIOS`, `SQUADS`, `LTM`), incluindo as labels dinâmicas (ex. _Top 6_, _Top 12_) e o `Tracker Rating`.
- `ranks`: Rank Atual e Melhor Rank Histórico para os 4 modos competitivos do site.
- `partidas_recentes`: Agrupamento hierárquico das sessões de jogo dos últimos dias, revelando Kills/Outlived/Score individuais por partida.
