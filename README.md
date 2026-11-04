# Progressão Automatizada UFPA (Lattes)

Importação de currículos Lattes e pontuação para progressão funcional docente.

Ferramenta web (Flask + SQLite) que:

1. Lê um CSV com IDs Lattes de professores da UFPA (ou IDs digitados) e baixa os currículos no
   **eLattes UFPA** (https://elattes.ufpa.br/) automaticamente: `POST /download_cvs` → `GET /progress/<job>`
   → `GET /download_file/<job>` (zip com `<id>.zip` → `<id>.xml`), extrai o XML e importa.
2. Gera a **página de perfil** do professor com todos os itens do Lattes (formação, atuação, projetos,
   produção bibliográfica/técnica, orientações, bancas, eventos, prêmios…) e uma aba **Pontuação**
   com quantidade × valor por item do Anexo I (Quadro de Atividades Referenciais) e totais por grupo.
3. Mostra no perfil o botão **azul "Atualizar"** quando o eLattes informa uma versão mais nova do currículo
   (`POST /get_last_update`) ou **verde "Currículo Atualizado"** quando a versão importada é a mais recente.
4. **Camada de gestão** (`/admin`, usuário `admin`, senha `senha`):
   - Professores incorporados, com data da última atualização no Lattes, data de importação e status;
   - Importar (CSV/IDs via eLattes ou upload manual de zip/xml);
   - Tabela de valores: o admin atribui o valor de cada um dos 175 itens (gradações como 24/12 viram variantes `.a/.b`);
   - Mapeamento Lattes → Tabela: define a qual item cada tipo de registro do Lattes é associado;
   - Exportação CSV da pontuação de todos os professores.

## Análise por interstício e grupos

- No perfil (aba **Pontuação**) e na lista da gestão há um filtro com **ano inicial/final do interstício**
  e os **grupos (I–VIII) considerados**. Atalhos: últimos 2–3 anos e "todo o currículo".
- Entra na análise todo registro cujo período intercepta o interstício; itens contados por ano
  (projetos, cargos, revisão de periódico) contam só os anos dentro dele.
- Grupos desmarcados continuam visíveis, mas não somam no total. Na aba Currículo, itens fora do
  interstício aparecem esmaecidos.
- O padrão (usado quando a página abre sem filtro) é definido em **Gestão → Configuração**; a exportação
  CSV usa o filtro da tela.
- A logo da UFPA é enviada em **Gestão → Configuração → Logo** e fica guardada no disco do servidor.

## Fotos dos professores

A foto vem do serviço oficial de fotos do CNPq (`servicosweb.cnpq.br/wspessoa/servletrecuperafoto`), que usa o
identificador interno do CNPq (K0000000A0). Esse identificador é obtido apenas lendo o redirecionamento de
`lattes.cnpq.br/<ID>`; o currículo não é aberto. A miniatura (320×320) fica em `DATA_DIR/fotos/` e é buscada de novo
quando o currículo é reimportado. Sem foto, aparece a inicial; nova tentativa só após 24 h.
Pode ser desligado em **Gestão → Configuração → Fotos dos professores**.

## Executar

```bash
pip install -r requirements.txt
python app.py            # http://localhost:5000
```

Variáveis opcionais: `ADMIN_USER`, `ADMIN_PASS`, `SECRET_KEY`, `PORT`.
Os dados ficam em `data/app.db` e os XMLs em `data/curriculos/`.

## Deploy no Render

1. No Render: **New → Blueprint** e selecione este repositório (ele lê o `render.yaml`).
2. Informe `ADMIN_USER` e `ADMIN_PASS` quando solicitado (`SECRET_KEY` é gerada automaticamente).
3. O serviço sobe com gunicorn (1 processo, 8 threads) e um disco persistente de 1 GB em `/var/data`,
   onde ficam o banco e os XMLs.

Observações:
- O disco persistente exige plano pago (Starter). No plano grátis funciona, mas o banco é apagado a cada
  deploy/reinício e o serviço hiberna após inatividade (troque `plan: starter` por `plan: free` e remova o bloco `disk`).
- Mantenha **1 worker** (`-w 1`): o progresso das importações fica em memória.

## Teste rápido

1. Entre em **Gestão** (admin/senha) → **Importar**.
2. Deixe o ID de teste `9157422386900321` (ou envie `professores.csv`) e clique em **Baixar do eLattes e importar**.
3. Acompanhe o progresso; ao concluir, abra o perfil do professor e a aba **Pontuação**.
4. Em **Tabela de valores**, altere um valor e veja a pontuação recalculada no perfil.

Sem acesso ao eLattes, use a importação manual com `tests/exemplo_9157422386900321.xml`
(XML de exemplo no formato oficial, ISO-8859-1).

## Estrutura

| Arquivo | Função |
|---|---|
| `app.py` | Rotas Flask, banco SQLite, jobs de importação em segundo plano |
| `elattes_client.py` | Cliente do eLattes (download em lote, progresso, zip aninhado, última atualização) |
| `lattes_parser.py` | Parser do XML do Lattes → seções do perfil + contagem por categoria |
| `scoring.py` | Tabela do Anexo I (8 grupos), categorias do Lattes, mapeamento padrão e cálculo |
| `templates/`, `static/` | Interface |

## Regras de contagem (ajustáveis em Mapeamento)

- Artigos: idioma ≠ Português → "internacional" (VIII.11), senão "nacional" (VIII.12).
- Capítulos/livros organizados: país de publicação ≠ Brasil → internacional.
- Trabalhos em eventos: `COMPLETO`/`RESUMO_EXPANDIDO` → VIII.23 (ou VIII.68 se evento regional/local); `RESUMO` → VIII.24.
- Projetos: o docente é "coordenador" quando aparece como `FLAG-RESPONSAVEL="SIM"`; financiamento interno
  quando o financiador contém UFPA/PROPESP/PROEX; itens "por ano" multiplicam pelos anos de duração.
- Orientações/bancas: pelo tipo de elemento do XML (mestrado, doutorado, qualificação, TCC, IC, concurso…).
- Prêmios: heurística de nome/entidade em inglês ou "internacional" → VI.19.a, senão VI.19.b.
- Cursos ministrados: a cada 3 h (IV.4). Software com `REGISTRO-OU-PATENTE` → VIII.63. Patente com data de concessão → VIII.36.
- Itens sem correspondência no Lattes (carga horária de aulas, bolsa PQ, cargos) ficam como "não pontua"
  por padrão e podem ser mapeados pelo admin.
