# RackRoute API

Projeto de portfólio em Python para calcular rotas físicas de cabeamento entre
racks de um Data Center simulado.

## Estado atual

Aplicação FastAPI com `GET /health` e núcleo reutilizável de pathfinding com A*,
Manhattan e testes. Os modelos de domínio, o carregamento JSON e o frontend ainda
não foram implementados.

## Requisitos

- Python 3.12 ou superior.
- Dependências e ferramentas de desenvolvimento definidas em `pyproject.toml`.

## Instalação e execução

Na raiz do repositório, usando PowerShell no Windows:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m uvicorn api.main:app --reload
```

Se `.venv` já existir com Python 3.12+, omita o primeiro comando. Não é necessário
ativar o ambiente para usar os comandos acima.

- API: http://127.0.0.1:8000
- Documentação interativa: http://127.0.0.1:8000/docs

## Verificar a aplicação

Com o servidor em execução, abra outro terminal PowerShell:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health | ConvertTo-Json -Compress
```

Resposta esperada, com HTTP 200:

```json
{"status":"ok"}
```

## Estrutura e responsabilidades

```text
src/
  pathfinding/                # Núcleo genérico A*, sem dependência do domínio
  datacenter/
    models/                   # Entidades e objetos de valor
    services/                 # Casos de uso, incluindo CableRouteService
    infrastructure/           # Carregamento de layouts JSON
  api/                        # FastAPI, contratos HTTP e montagem da aplicação
frontend/                     # HTML, CSS e JavaScript puro (a implementar)
data/                         # Layouts JSON (a adicionar)
tests/
  pathfinding/
  datacenter/
  api/
```

`src` é o diretório de código-fonte, não um pacote Python. A instalação editável
torna os pacotes disponíveis sem modificar `PYTHONPATH`.

## Arquitetura

Fluxo previsto: Frontend → FastAPI → CableRouteService → Domínio → Pathfinding.

- A API chama os serviços e conecta suas dependências na inicialização.
- Os serviços usam os modelos de domínio e o núcleo de pathfinding.
- A infraestrutura carrega JSON e constrói os modelos de domínio.
- O domínio não depende de FastAPI nem da camada HTTP.
- O núcleo depende apenas da biblioteca padrão; nunca importa `datacenter` ou `api`.
- A* usa `heapq` e aceita uma heurística; Manhattan atende grids ortogonais de custo unitário.
- Modelos e objetos de valor usarão dataclasses quando adequado, com type hints.

## Testes

Os testes do núcleo cobrem Manhattan, caminhos livres e com obstáculos, destino
inacessível, origem igual ao destino, custos variados, desempates entre objetos
não ordenáveis, entradas antigas da fila, reabertura de nós e custos inválidos.

```powershell
.\.venv\Scripts\python.exe -m pytest
```

A verificação manual do endpoint está descrita acima. Os testes de domínio e API
serão adicionados nas próximas etapas.

## Contrato do núcleo

- `Graph` define apenas `neighbors(node)` e `cost(current, neighbor)`.
- Nós devem ser hashable, com igualdade e hash estáveis. Não precisam ser ordenáveis.
- `AStar.search(graph, start, goal, heuristic)` retorna `PathResult`.
- A heurística deve ser finita, não superestimar o custo restante e valer zero no destino.
- Custos de arestas devem ser finitos e não negativos; valores inválidos encontrados
  durante a busca geram `ValueError`.
- `manhattan` recebe pares `(x, y)`. Outros tipos de nós podem usar outra função
  ou uma função que adapte suas coordenadas para Manhattan.
- `path` inclui origem e destino; `total_cost` soma os custos das arestas.
- Sem caminho, o resultado é `path=[]` e `total_cost=math.inf`.
- `explored_nodes` conta remoções válidas da fila, incluindo o destino e eventuais
  reaberturas. Entradas antigas descartadas não contam.
- A busca pressupõe um grafo finito. Uma heurística constante zero equivale a Dijkstra.

A busca remove o menor `g + h` da fila, examina seus vizinhos e registra somente
melhorias de custo. Ao retirar o destino, reconstrói o caminho pelos predecessores.
Se a fila esvaziar, retorna o resultado de ausência de caminho.

## Limites do MVP

Layouts inicialmente em JSON. Sem banco de dados, autenticação, microserviços,
Docker, bibliotecas externas de grafos/pathfinding ou framework de frontend.

## Próximas etapas

- Adicionar domínio, carregamento JSON e CableRouteService.
- Expor as rotas HTTP e construir a interface visual mínima.
