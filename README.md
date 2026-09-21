# RackRoute API

Projeto de portfólio em Python para calcular rotas físicas de cabeamento entre
racks de um Data Center simulado.

## Estado atual

Aplicação FastAPI com endpoints de consulta e roteamento e núcleo reutilizável com A*,
Manhattan e testes. O domínio inclui Position, Rack, DataCenterLayout e CableRoute.
CableRouteService calcula rotas e comprimentos físicos. O carregador JSON valida
arquivos e constrói layouts de domínio. Um painel HTML/CSS/JavaScript permite
selecionar racks, visualizar o grid e consultar rotas pela API.

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
frontend/                     # Painel HTML, CSS e JavaScript puro
data/                         # Layout JSON de exemplo
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
- Os modelos de domínio usam dataclasses, com type hints e coleções imutáveis.

## Testes

Os testes do núcleo cobrem Manhattan, caminhos livres e com obstáculos, destino
inacessível, origem igual ao destino, custos variados, desempates entre objetos
não ordenáveis, entradas antigas da fila, reabertura de nós e custos inválidos.

```powershell
.\.venv\Scripts\python.exe -m pytest
```

A suíte também valida os modelos de domínio, os movimentos permitidos no layout,
as invariantes dos dados e a integração com o A* existente. A verificação manual
do endpoint está descrita acima. Testes de integração com FastAPI TestClient
validam os endpoints, schemas, erros HTTP e carregamento na inicialização.

## Domínio de Data Center

- `Position(x, y)` é imutável, comparável por valor e hashable. `as_tuple()` permite
  adaptar suas coordenadas à função Manhattan sem modificar o núcleo.
- `Rack(id, position)` identifica um rack em uma posição do grid.
- `DataCenterLayout(width, height, cell_size_meters, racks, blocked_positions)`
  valida dimensões, tamanho da célula, IDs únicos e posições de racks e bloqueios.
  Racks não podem ficar fora do mapa ou em células bloqueadas.
- O layout satisfaz `Graph[Position]` estruturalmente por `neighbors` e `cost`.
  Permite apenas movimentos ortogonais entre células livres, com custo 1.
  O tamanho físico da célula não altera o custo do grafo.
- As coordenadas começam em zero. Células com racks são transitáveis, e
  `get_rack(id)` retorna o rack ou lança `KeyError` quando o ID não existe.
- `CableRoute` é um resultado de domínio com racks de origem/destino, caminho,
  passos, distância em metros, comprimento recomendado e nós explorados.
  O serviço monta esse resultado e calcula as métricas físicas.

### Serviço de roteamento

`CableRouteService(layout).calculate_route(source_rack_id, destination_rack_id,
safety_margin=0.10)` localiza os racks e executa A* com Manhattan. O resultado
contém `steps = len(path) - 1`, `distance_meters = steps * cell_size_meters` e
`recommended_cable_length_meters = distance_meters * (1 + safety_margin)`.

A margem é uma fração: `0.10` representa 10%. Zero é permitido; valores negativos,
não finitos e não numéricos são rejeitados. Não há limite percentual superior.
A validação ocorre na ordem: margem, rack de origem, rack de destino, busca.

Exceções em `datacenter.exceptions`, sem dependência de HTTP:

- `RackNotFoundError`: rack inexistente, identificado por `rack_id`.
- `NoRouteAvailableError`: não há caminho entre os racks informados.
- `InvalidSafetyMarginError`: margem inválida.

Todas derivam de `CableRouteError`. Origem igual ao destino retorna um caminho
com uma posição, zero passos e comprimentos iguais a zero.

Os testes do serviço usam o A* real e cobrem cálculos, desvio de obstáculos,
margens, racks ausentes, ausência de rota e origem igual ao destino.

Exemplo de integração com o núcleo:

```python
from pathfinding.astar import AStar
from pathfinding.manhattan import manhattan

result = AStar.search(
    layout,
    source.position,
    destination.position,
    lambda current, goal: manhattan(current.as_tuple(), goal.as_tuple()),
)
```

Nesse exemplo, `layout`, `source` e `destination` são objetos de domínio já
construídos. O núcleo continua sem importar o domínio ou FastAPI.

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

## Carregamento de layouts JSON

```python
from datacenter.infrastructure import load_layout
from datacenter.services import CableRouteService

layout = load_layout("data/example_datacenter.json")
route = CableRouteService(layout).calculate_route("RACK-A23", "RACK-D17")
```

O caminho pode ser `str` ou `Path`; caminhos relativos são resolvidos a partir do
diretório de execução. O arquivo deve ser UTF-8 e conter `width`, `height`,
`cell_size_meters`, `racks` e `blocked_cells`. Cada rack contém `id`, `x` e `y`;
cada célula bloqueada é um par `[x, y]`. As listas podem estar vazias.

Schemas Pydantic privados à infraestrutura validam tipos estritos, campos
obrigatórios, campos desconhecidos, dimensões positivas, tamanho de célula finito
e positivo e pares de coordenadas inteiras. Os modelos de domínio continuam
responsáveis pelas regras de limites, IDs duplicados e racks em células bloqueadas.
O carregador converte racks e coordenadas em objetos `Rack` e `Position`.

Falhas de leitura, JSON inválido ou layout inconsistente geram `LayoutLoadError`,
com o caminho do arquivo e a causa original preservada. Os modelos de domínio
não importam JSON ou Pydantic.

O exemplo fornecido produz 14 passos, 7 metros e recomendação de 7,7 metros com a
margem padrão de 10%. Os testes validam esse fluxo e arquivos malformados.

## API REST

A aplicação carrega `data/example_datacenter.json` uma vez na inicialização,
usando um caminho relativo ao repositório, independente do diretório do terminal.
Arquivo inválido interrompe a inicialização. `create_app(layout_path)` permite
selecionar outro arquivo ao montar a aplicação, inclusive nos testes.

| Método | Endpoint | Resultado |
| --- | --- | --- |
| GET | `/health` | `{"status":"ok"}` |
| POST | `/api/v1/routes` | Caminho genérico, custo total e nós explorados |
| POST | `/api/v1/cable-routes` | Caminho entre racks e métricas físicas |
| GET | `/api/v1/racks` | Lista de objetos com `id`, `x` e `y` |
| GET | `/api/v1/layout` | Dimensões, tamanho da célula, racks e `blocked_cells` |

Requisição para `/api/v1/routes` (coordenadas `[x, y]`):

```json
{
  "width": 3,
  "height": 3,
  "start": [0, 0],
  "goal": [2, 0],
  "blocked_cells": [[1, 0]]
}
```

`blocked_cells` é opcional e usa lista vazia por padrão. A resposta contém
`route`, `total_cost`, `explored_nodes`, `algorithm` e `heuristic`. O grid é
independente do Data Center carregado e usa movimentos ortogonais de custo 1.

Requisição para `/api/v1/cable-routes`:

```json
{
  "source_rack": "RACK-A23",
  "destination_rack": "RACK-D17",
  "safety_margin": 0.10
}
```

`safety_margin` é opcional e usa 10% por padrão. A resposta contém `source`,
`destination`, `route` (caminho completo), `steps`, `distance_meters`,
`recommended_cable_length_meters`, `explored_nodes`, `algorithm: "A*"` e
`heuristic: "Manhattan"`. As métricas são calculadas a partir do caminho real.

Erros são JSON com campo `detail`:

- **400:** margem negativa, traduzida de `InvalidSafetyMarginError`.
- **404:** rack inexistente, traduzido de `RackNotFoundError`.
- **422:** ausência de rota, JSON malformado ou falha de schema (campos ausentes,
  tipos incorretos, números não finitos, posições inválidas ou bloqueadas).
- **200:** origem igual ao destino, com caminho de uma posição e custo zero.

Pydantic valida a fronteira HTTP; schemas de resposta convertem explicitamente
os objetos internos para JSON. A tradução HTTP fica em `api`, sem alterar o
domínio ou o A*. A documentação interativa está em `/docs`.

## Frontend

Com o Uvicorn em execução, abra http://127.0.0.1:8000/ . O próprio FastAPI serve
a página inicial e os arquivos CSS/JS em `/static`; não há etapa de build ou npm.

O painel carrega `/api/v1/layout` e `/api/v1/racks`. Selecione origem, destino e
margem percentual (10 significa 10%), depois clique em **Calculate Route**.
O navegador converte a porcentagem para a fração esperada pela API e envia
`POST /api/v1/cable-routes`. Apenas o backend calcula a rota e seus comprimentos.

O CSS Grid diferencia células livres, bloqueios, racks, origem, destino e rota.
`S` e `G` marcam os extremos; `S/G` indica uma posição compartilhada. O resumo
mostra origem, destino, passos, distância, cabo recomendado, nós explorados,
algoritmo e heurística. Comprimentos são apresentados com até duas casas decimais.

Alterar parâmetros limpa o resultado anterior. O formulário é desativado durante
requisições, erros são exibidos na página e **Reload layout** permite repetir o
carregamento. Como o backend mantém o layout em memória, alterações no JSON
exigem reiniciar o servidor. O indicador API reflete a última requisição, sem
monitoramento periódico. Em telas estreitas, os painéis ficam em uma coluna e
grids maiores podem ser rolados horizontalmente.

## Limites do MVP

Layouts inicialmente em JSON. Sem banco de dados, autenticação, microserviços,
Docker, bibliotecas externas de grafos/pathfinding ou framework de frontend.
