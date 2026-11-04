# -*- coding: utf-8 -*-
"""
Tabela de pontuação (Anexo I – Quadro de Atividades Referenciais) e
mapeamento entre as categorias extraídas do Lattes e os itens da tabela.

Chave de item: "<GRUPO>.<NUMERO>" (ex.: "VIII.11"). Itens com gradação
(ex.: 24/12) são desdobrados em variantes "<GRUPO>.<NUMERO>.<letra>".
"""

GRUPOS = {
    "I": "Docência / Atividades de ensino / Desempenho didático (por semestre)",
    "II": "Atividades de orientação",
    "III": "Participação em bancas examinadoras",
    "IV": "Atividades de extensão",
    "V": "Atividades de pesquisa",
    "VI": "Atividades administrativas e de representação",
    "VII": "Atividades de capacitação (no interstício)",
    "VIII": "Produção científica, de inovação, técnica ou artística (por unidade)",
}

# (grupo, numero, atividade, pontuação de referência)
# A pontuação pode ser um número ou uma lista de (sufixo_label, valor) para gradações.
TABELA_RAW = [
    # GRUPO I
    ("I", 1, "Aulas efetivas em Curso de Graduação, observada a legislação vigente (a cada 60 h por semestre).", 10),
    ("I", 2, "Aulas efetivas em Curso de Pós-Graduação stricto sensu, observada a legislação vigente (a cada 30 h por semestre).", 10),
    ("I", 3, "Aulas em cursos de Residência em saúde (por bloco de carga horária equivalente).", 10),
    ("I", 4, "Orientação acadêmica de alunos de graduação, nos termos do Regulamento de Graduação (por aluno/semestre).", 1),
    ("I", 5, "Estágio em docência assistida realizado durante curso de Pós-Graduação stricto sensu, validado pela instituição (por aluno/semestre).", 2),
    ("I", 6, "Coordenação ou participação como membro em programa/projeto de ensino ou de inovação pedagógica concluído, com duração mínima de 1 ano e certificação institucional (por projeto).", [("coordenação", 24), ("membro", 12)]),
    ("I", 7, "Acompanhamento pedagógico de estudantes com necessidades educacionais específicas ou com deficiência, na graduação e pós-graduação (por aluno/mês).", 1),
    ("I", 8, "Adicional para turmas com mais de 90 alunos matriculados, dividido proporcionalmente entre os docentes da turma (por turma).", 8),
    # GRUPO II
    ("II", 1, "Tutoria de Pós-Doutorado concluída (por aluno).", 20),
    ("II", 2, "Orientação de Tese de Doutorado defendida (por aluno).", 30),
    ("II", 3, "Orientação de Dissertação de Mestrado defendida (por aluno).", 20),
    ("II", 4, "Coorientação de Tese de Doutorado defendida (por aluno).", 15),
    ("II", 5, "Coorientação de Dissertação de Mestrado defendida (por aluno).", 10),
    ("II", 6, "Orientação de Monografia ou TCC de Curso de Especialização não remunerada concluída (por aluno).", 15),
    ("II", 7, "Orientação de TCC de Curso de Graduação, técnico e tecnológico defendido (por aluno).", 10),
    ("II", 8, "Orientação de aluno em programas/projetos institucionais de pesquisa, inovação, ensino e extensão – PIBIC, JTC e similares (por aluno).", 10),
    ("II", 9, "Orientação de aluno em programa de bolsa permanência, mobilidade acadêmica, bolsa instrutor, voluntariado acadêmico ou supervisão de aluno de pós-graduação nas atividades de graduação/curso técnico (por aluno).", 5),
    ("II", 10, "Tutorial de Grupo PET e de residência médica (por ano de exercício).", 15),
    ("II", 11, "Orientação de aluno do Grupo PET (por ano).", 5),
    ("II", 12, "Orientação de aluno em estágios – estágio supervisionado, exceto os obrigatórios das licenciaturas e bacharelados (por aluno/ano).", 6),
    ("II", 13, "Orientação de aluno em programa de monitoria (por aluno).", 5),
    ("II", 14, "Orientação de aluno no PIBIC (por aluno) e no PIBID (por aluno).", 11),
    ("II", 15, "Coordenador de estágio supervisionado/curricular obrigatório (por ano).", 5),
    ("II", 16, "Orientação de Tese de Doutorado em andamento (por aluno).", 15),
    ("II", 17, "Orientação de Dissertação de Mestrado em andamento (por aluno).", 10),
    ("II", 18, "Orientação de TCC de Graduação e técnico em andamento (por aluno).", 5),
    ("II", 19, "Supervisão de estágio de Pós-Doutorado ou de Doutorado-sanduíche, exceto quando o supervisor for coorientador (por supervisionado/mês).", 2),
    # GRUPO III
    ("III", 1, "Membro de Banca Examinadora de livre-docência ou Tese de Doutorado (por banca).", 10),
    ("III", 2, "Membro de Banca Examinadora de Dissertação de Mestrado (por banca).", 8),
    ("III", 3, "Membro de Banca Examinadora de Monografia ou TCC de Curso de Especialização não remunerada (por banca).", 5),
    ("III", 4, "Membro de Banca Examinadora de TCC de Curso de Graduação ou curso técnico (por banca).", 3),
    ("III", 5, "Membro de Banca de concurso público para professor substituto (por banca).", 5),
    ("III", 6, "Membro de Banca de concurso público para Professor da Carreira do Magistério Superior ou do EBTT – professor efetivo (por banca).", 10),
    ("III", 7, "Membro de Banca de qualificação em cursos de pós-graduação (por banca).", 5),
    ("III", 8, "Membro de Banca de seleção para pós-graduação (por banca).", 3),
    ("III", 9, "Membro de Banca de seleção para bolsas institucionais (por banca).", 2),
    ("III", 10, "Membro de Banca de avaliação e seleção para atividades culturais e artísticas (por banca).", 5),
    ("III", 11, "Membro de Banca de processo seletivo (por banca).", 5),
    ("III", 12, "Membro de Banca de teste de habilidades (por banca).", 5),
    ("III", 13, "Membro de Banca de Avaliação de Desempenho para fins de Progressão e Promoção Docente (por banca).", 10),
    # GRUPO IV
    ("IV", 1, "Coordenação e execução de Programa/Projeto de Extensão ou PAPIM, desde que a ação não seja contemplada com remuneração adicional (por ano, com relatório final).", 15),
    ("IV", 2, "Participação em Programa/Projeto de Extensão registrado (por ano).", 8),
    ("IV", 3, "Coordenação de curso de extensão, sem remuneração adicional, mediante comprovação com ano/período (a cada 20 h).", 10),
    ("IV", 4, "Ministrante de curso de extensão, mediante comprovação com ano/período (a cada 3 h).", 2),
    ("IV", 5, "Ministrante de curso de aperfeiçoamento ou de formação continuada (a cada 3 h).", 3),
    ("IV", 6, "Coordenação de evento de extensão, mediante comprovação com ano/período (a cada 15 h).", 5),
    ("IV", 7, "Ministrante de evento de extensão, mediante comprovação com ano/período (a cada 3 h).", 2),
    ("IV", 8, "Orientação de bolsista de ação de extensão (por projeto/mês, limitado a 30).", 1),
    ("IV", 9, "Divulgação científica em mídias digitais, na área de atuação do docente (por produto).", [("internacional", 3), ("nacional", 2), ("local", 1)]),
    # GRUPO V
    ("V", 1, "Coordenação e execução de projeto de pesquisa registrado na Unidade e na PROPESP, sem financiamento (por projeto, mediante relatório final).", 20),
    ("V", 2, "Coordenação de projeto de pesquisa registrado na PROPESP com financiamento interno (por projeto/ano).", 20),
    ("V", 3, "Coordenação de projeto de pesquisa registrado na PROPESP com financiamento externo (por projeto/ano).", 25),
    ("V", 4, "Participação em projeto de pesquisa registrado na PROPESP sem financiamento (por projeto/ano).", 10),
    ("V", 5, "Participação em projeto de pesquisa registrado na PROPESP com financiamento interno (por ano).", 15),
    ("V", 6, "Participação em projeto de pesquisa registrado na PROPESP com financiamento externo (por ano).", 20),
    ("V", 7, "Coordenação/liderança de grupo de pesquisa registrado na UFPA/CNPq (por ano de exercício).", 15),
    ("V", 8, "Membro de grupo de pesquisa registrado na UFPA/CNPq (por ano de exercício).", 10),
    ("V", 9, "Coordenação de núcleo de pesquisa registrado na UFPA (por ano de exercício ou por projeto, mediante relatório).", 15),
    ("V", 10, "Bolsa de produtividade em pesquisa do CNPq (por ano).", [("nível 1", 25), ("nível 2", 20)]),
    ("V", 11, "Consultoria/parecer ad hoc de projeto e de bolsas junto à CAPES/CNPq (por parecer).", 10),
    ("V", 12, "Consultoria/parecer de projeto registrado na PROPESP ou na PROEX (por parecer).", 6),
    ("V", 13, "Coordenação/gerência de processo de incubação (pré-incubação/incubação) aprovado pelas instâncias competentes (por mês).", 1),
    ("V", 14, "Tutoria em Empresa Júnior ou em Incubadora (por empresa/mês).", 1),
    # GRUPO VI
    ("VI", 1, "Reitor e Vice-Reitor (por ano de exercício).", 70),
    ("VI", 2, "Pró-Reitor (por ano de exercício).", 50),
    ("VI", 3, "Coordenador de Campus, Diretor-Geral de Unidade Acadêmica, Diretor de Unidade Acadêmica de EBTT (por ano de exercício).", 50),
    ("VI", 4, "Vice-Coordenador de Campus, Diretor-Adjunto de Unidade Acadêmica, Vice-Diretor de EBTT, Diretor de Órgão Suplementar, Diretor de Pró-Reitoria (por ano de exercício).", 40),
    ("VI", 5, "Presidente de Comissão de Assessoramento Superior (CPPD, CPPDA) (por ano de exercício).", 25),
    ("VI", 6, "Diretor de Faculdade/Escola, Coordenador de Curso de Pós-Graduação stricto sensu, Vice-Presidente de Comissão de Assessoramento Superior/CPPD, membro titular de Órgão Colegiado Superior (por ano de exercício).", 30),
    ("VI", 7, "Vice-Diretor de Faculdade/Escola, Vice-Coordenador de PPG stricto sensu, Coordenador de Curso de Graduação/Tecnológico/Técnico, membro de Comissão de Assessoramento Superior e da CPPD, Coordenador Geral de Congresso Internacional, membro titular das Câmaras dos Conselhos Superiores e suplente de Órgão Colegiado Superior (por ano de exercício).", 20),
    ("VI", 8, "Coordenador de Projetos de Intercâmbios Internacionais, Coordenador Geral de Congresso Nacional, membro da Central de Processos Seletivos/Núcleo de Concursos, Diretoria da Seção-Sindical/ADUFPA ou do ANDES, Presidente do NDE, Presidente da CPA, Coordenação de Núcleos Internos da EMUFPA, Presidente das Câmaras das Unidades e Subunidades Acadêmicas (por ano).", 10),
    ("VI", 9, "Coordenador de Curso de Especialização lato sensu sem remuneração (por ano de exercício).", 10),
    ("VI", 10, "Membro de Comissão constituída por ato da Administração Superior; membro de Comitê de Pesquisa/Estágio/Extensão; Comitê de Ética; representante designado em órgãos de C&T e Cultura; Coordenador de Convênio Institucional; Coordenador de Comitês; Coordenador Geral de Congresso Regional; Secretário Executivo de Congresso; membro das Câmaras das Unidades; membro de Câmara de TCC; membro de Associações/Conselhos/Comitês Setoriais; Coordenador de espaços culturais (por designação/ano).", 7),
    ("VI", 11, "Membro de Comitê Editorial de publicação indexada (por ano).", 8),
    ("VI", 12, "Vice-Coordenador de Curso de Especialização; membro de Comissão constituída por ato da Administração da Unidade; membro de comissão de sindicância/PAD; membro da Comissão de Relações Internacionais; membro de Comissão Organizadora de congresso/seminário/simpósio/jornada/encontro (por designação/ano).", 3),
    ("VI", 13, "Membro titular ou suplente de colegiado de curso Técnico/Tecnológico, de conselho/colegiado de subunidade e congregação de unidade; coordenador geral de outras atividades técnicas/científicas/culturais/artísticas/desportivas; organização de processo seletivo – PSS/vestibular (por ano).", 5),
    ("VI", 14, "Membro titular ou suplente de Conselho Escolar; Comitê de Usuários de Bibliotecas; assessoria técnica e consultorias autorizadas em plenária; Banca de Seleção de Bolsistas e Professores Temporários; supervisores e preceptores de residência médica; outras comissões (por ano).", 6),
    ("VI", 15, "Chefia ou coordenação de laboratório de ensino, pesquisa ou extensão (por ano).", 10),
    ("VI", 16, "Membro de Comissões do MEC – SINAES, BASIS, ENADE, ENEM e similares (por ano).", 10),
    ("VI", 17, "Tutor de docente em estágio probatório (por mês).", 1),
    ("VI", 18, "Título honorífico concedido por sociedade ou colégio de especialistas credenciados (por título).", [("internacional", 15), ("nacional", 10), ("regional/local", 5)]),
    ("VI", 19, "Prêmio de mérito profissional ou acadêmico (por prêmio).", [("internacional", 20), ("nacional", 15), ("regional/local", 10)]),
    ("VI", 20, "Obra cultural ou artística premiada (por obra).", [("internacional", 15), ("nacional", 10), ("regional/local", 7)]),
    # GRUPO VII
    ("VII", 1, "Doutor ou Livre-Docente.", 90),
    ("VII", 2, "Mestre.", 60),
    ("VII", 3, "Pós-Doutorado realizado por meio de programa institucional.", 30),
    ("VII", 4, "Estágio de Pós-Doutorado concluído.", 15),
    ("VII", 5, "Créditos de Doutorado concluídos no interstício.", 20),
    ("VII", 6, "Créditos de Mestrado concluídos no interstício.", 10),
    ("VII", 7, "Curso de Especialização concluído (360 h).", 10),
    ("VII", 8, "Curso de aperfeiçoamento concluído (180 h).", 5),
    ("VII", 9, "Curso de extensão com frequência e aproveitamento (por curso).", 2),
    ("VII", 10, "Participação em congresso, simpósio, seminário ou outros cursos de curta duração (por participação).", 1),
    ("VII", 11, "Estágio de capacitação técnica (cada 30 h = 1 ponto).", 1),
    ("VII", 12, "Curso de língua estrangeira (por semestre).", 1),
    # GRUPO VIII
    ("VIII", 1, "Autor de livro publicado (com ISBN), na área, em editora que faça uso de pareceristas.", 50),
    ("VIII", 2, "Autor de livro publicado (com ISBN), na área, em editora que não faça uso de pareceristas.", 20),
    ("VIII", 3, "Autor de capítulo publicado de coletânea (com ISBN), com circulação internacional.", 20),
    ("VIII", 4, "Autor de capítulo publicado de coletânea (com ISBN), de editora nacional.", 15),
    ("VIII", 5, "Tradução de livro publicado (impresso ou eletrônico).", 30),
    ("VIII", 6, "Tradução de texto teatral, roteiro de cinema, vídeo, rádio ou televisão.", 20),
    ("VIII", 7, "Tradução de parte de texto teatral, roteiro de cinema, vídeo, rádio ou televisão.", 10),
    ("VIII", 8, "Tradução de capítulo de livro publicado (impresso ou eletrônico).", 10),
    ("VIII", 9, "Editor ou organizador de livro publicado (com ISBN), com circulação internacional.", 35),
    ("VIII", 10, "Editor ou organizador de livro publicado (com ISBN), com circulação nacional.", 20),
    ("VIII", 11, "Artigo de pesquisa publicado em revista indexada (ISSN), internacional, registrada no Qualis CAPES na área.", 35),
    ("VIII", 12, "Artigo de pesquisa publicado em revista indexada (ISSN), nacional, registrada no Qualis CAPES na área.", 25),
    ("VIII", 13, "Artigo de pesquisa publicado em revista não indexada.", 10),
    ("VIII", 14, "Publicação em sítio eletrônico especializado (internet).", 2),
    ("VIII", 15, "Artigo de revisão, resenha ou nota crítica publicado em revista indexada (ISSN).", 6),
    ("VIII", 16, "Artigo de revisão, resenha ou nota crítica publicado em revista não indexada (ISSN).", 5),
    ("VIII", 17, "Tradução publicada de artigo (impresso ou eletrônico).", 5),
    ("VIII", 18, "Artigo de imprensa interna ou externa à UFPA (impresso ou eletrônico).", 3),
    ("VIII", 19, "Relatório técnico demandado à UFPA na forma de consultoria.", 5),
    ("VIII", 20, "Produção de manual técnico e didático.", 7),
    ("VIII", 21, "Revisão de material didático, artigos, capítulo de livro, livros, resumos, abstracts, normas da ABNT.", 2),
    ("VIII", 22, "Nota científica prévia.", 2),
    ("VIII", 23, "Autor de trabalho completo ou resumo expandido publicado em congresso, simpósio ou seminário nacional ou internacional.", 10),
    ("VIII", 24, "Comunicação de trabalho com resumo publicado.", 2),
    ("VIII", 25, "Comunicação de trabalho sem resumo publicado.", 1),
    ("VIII", 26, "Apresentação de trabalho em seminários, congressos, simpósios e eventos artísticos ou científicos internacionais.", 8),
    ("VIII", 27, "Apresentação de trabalho em seminários, congressos, simpósios e eventos artísticos ou científicos nacionais.", 5),
    ("VIII", 28, "Participação como apresentador/conferencista/palestrante em conferências, palestras e mesas-redondas.", 5),
    ("VIII", 29, "Citação ou referência de autor(es) (por artigo ou livro).", 1),
    ("VIII", 30, "Ilustração de livros publicados (com conselho editorial).", 4),
    ("VIII", 31, "Criação de capa de livro publicado (com conselho editorial).", 4),
    ("VIII", 32, "Produção de livros (design).", 5),
    ("VIII", 33, "Texto escrito para catálogo de exposições publicado por instituição pública ou privada (com ISBN).", 15),
    ("VIII", 34, "Texto escrito para catálogo de exposições publicado por instituição pública ou privada (sem ISBN).", 8),
    ("VIII", 35, "Patente depositada requerida.", 10),
    ("VIII", 36, "Patente depositada concedida.", 30),
    ("VIII", 37, "Autor único de documentos cartográficos publicados.", 10),
    ("VIII", 38, "Coautor de documentos cartográficos publicados.", 5),
    ("VIII", 39, "Autoria de peça teatral ou musical publicada.", 30),
    ("VIII", 40, "Direção de peças teatrais apresentadas, cinema ou vídeo e de eventos musicais diversos (shows, recitais, concertos).", 15),
    ("VIII", 41, "Coreografia apresentada.", 15),
    ("VIII", 42, "Roteiro de cinema, vídeo, rádio ou televisão.", 15),
    ("VIII", 43, "Edição de partitura.", 7),
    ("VIII", 44, "Composição musical apresentada ou criada para cinema, vídeo, rádio, televisão, teatro ou dança.", 15),
    ("VIII", 45, "Arranjo de peças musicais, instrumental ou vocal.", 8),
    ("VIII", 46, "Exposições individuais referendadas pelo conselho de instituições reconhecidas.", 20),
    ("VIII", 47, "Autoria de curadoria de museus, exposições, mostras, festivais em espaços científicos, artísticos e culturais.", 20),
    ("VIII", 48, "Participação em salões de arte ou exposições coletivas de artes plásticas e fotografia referendadas.", 10),
    ("VIII", 49, "Produção de curadoria, exposições, mostras, festivais, espetáculos, cinema, rádio, TV, vídeo, audiovisual, mídias eletrônicas ou eventos musicais.", 15),
    ("VIII", 50, "Edição de rádio, cinema, vídeo ou televisão vinculada à atividade docente da UFPA.", 10),
    ("VIII", 51, "Obra de arte visual publicada.", 30),
    ("VIII", 52, "Produção musical de CD/DVD ou similares.", 15),
    ("VIII", 53, "Transcrição de obras musicais (por música ou parte de obra maior).", 8),
    ("VIII", 54, "Edição de obra musical.", 20),
    ("VIII", 55, "Composição musical com edição internacional.", 50),
    ("VIII", 56, "Composição musical com edição nacional.", 30),
    ("VIII", 57, "Recitais solo, camerísticos ou pequenos grupos em âmbito internacional, comprovado.", 25),
    ("VIII", 58, "Recitais solo, camerísticos ou pequenos grupos em âmbito nacional, comprovado.", 15),
    ("VIII", 59, "Execução musical em CD/DVD ou similares.", 20),
    ("VIII", 60, "Participação como convidado em festivais de música ou equivalentes, âmbito internacional.", 20),
    ("VIII", 61, "Participação como convidado em festivais de música ou equivalentes, âmbito nacional.", 10),
    ("VIII", 62, "Revisão de língua portuguesa ou estrangeira em revistas indexadas (por artigo).", 3),
    ("VIII", 63, "Registro de marcas, softwares e cultivares.", 15),
    ("VIII", 64, "Editor-Chefe de Revista.", 30),
    ("VIII", 65, "Editor Associado de Revista.", 20),
    ("VIII", 66, "Consultor ad hoc ou revisor de revista indexada (ano/revista).", 3),
    ("VIII", 67, "Parecerista em programas institucionais de pesquisa e extensão (no interstício).", 1),
    ("VIII", 68, "Autor de trabalho completo ou resumo expandido publicado em anais de evento regional/local.", 3),
    ("VIII", 69, "Prefácio, editorial ou introdução de livro ou de periódico científico (com ISBN/ISSN e conselho editorial).", 8),
    ("VIII", 70, "Carta patente (patente efetivamente concedida com carta expedida pelo INPI).", 50),
]


def tabela_itens():
    """Lista plana de itens, com variantes desdobradas.
    Retorna dicts: key, grupo, numero, variante, atividade, valor_padrao, ordem."""
    itens = []
    ordem = 0
    for grupo, numero, atividade, pont in TABELA_RAW:
        if isinstance(pont, list):
            for i, (rotulo, valor) in enumerate(pont):
                ordem += 1
                itens.append({
                    "key": f"{grupo}.{numero}.{chr(97 + i)}",
                    "grupo": grupo, "numero": numero, "variante": rotulo,
                    "atividade": f"{atividade} — {rotulo}",
                    "valor_padrao": float(valor), "ordem": ordem,
                })
        else:
            ordem += 1
            itens.append({
                "key": f"{grupo}.{numero}", "grupo": grupo, "numero": numero,
                "variante": "", "atividade": atividade,
                "valor_padrao": float(pont), "ordem": ordem,
            })
    return itens


# ---------------------------------------------------------------------------
# Categorias extraídas do Lattes -> item padrão da tabela
# (key, rótulo, grupo sugerido, item padrão ou None, modo de quantidade)
# modo: "count" = 1 unidade por registro; "years" = anos de duração;
#       "hours3" = a cada 3 h de duração
# ---------------------------------------------------------------------------
CATEGORIAS = [
    # Formação / capacitação
    ("form_doutorado", "Doutorado concluído", "VII", "VII.1", "count"),
    ("form_mestrado", "Mestrado concluído", "VII", "VII.2", "count"),
    ("form_posdoc", "Pós-doutorado concluído", "VII", "VII.4", "count"),
    ("form_especializacao", "Especialização concluída", "VII", "VII.7", "count"),
    ("form_curso_curta", "Formação complementar – curso de curta duração", "VII", "VII.9", "count"),
    ("form_outros", "Formação complementar – outros", "VII", None, "count"),
    ("evento_participante", "Participação em eventos (ouvinte/participante)", "VII", "VII.10", "count"),
    ("evento_palestrante", "Participação em eventos como conferencista/palestrante/moderador", "VIII", "VIII.28", "count"),
    # Orientações concluídas
    ("orient_posdoc_concl", "Supervisão de pós-doutorado concluída", "II", "II.1", "count"),
    ("orient_doutorado_concl", "Orientação de doutorado concluída", "II", "II.2", "count"),
    ("orient_mestrado_concl", "Orientação de mestrado concluída", "II", "II.3", "count"),
    ("coorient_doutorado_concl", "Coorientação de doutorado concluída", "II", "II.4", "count"),
    ("coorient_mestrado_concl", "Coorientação de mestrado concluída", "II", "II.5", "count"),
    ("orient_especializacao_concl", "Orientação de monografia de especialização concluída", "II", "II.6", "count"),
    ("orient_tcc_concl", "Orientação de TCC de graduação concluída", "II", "II.7", "count"),
    ("orient_ic_concl", "Orientação de iniciação científica concluída", "II", "II.8", "count"),
    ("orient_outra_concl", "Orientação de outra natureza concluída", "II", "II.9", "count"),
    # Orientações em andamento
    ("orient_posdoc_and", "Supervisão de pós-doutorado em andamento", "II", None, "count"),
    ("orient_doutorado_and", "Orientação de doutorado em andamento", "II", "II.16", "count"),
    ("orient_mestrado_and", "Orientação de mestrado em andamento", "II", "II.17", "count"),
    ("orient_tcc_and", "Orientação de TCC de graduação em andamento", "II", "II.18", "count"),
    ("orient_ic_and", "Orientação de iniciação científica em andamento", "II", None, "count"),
    ("orient_outra_and", "Outras orientações em andamento", "II", None, "count"),
    # Bancas
    ("banca_doutorado", "Banca de doutorado", "III", "III.1", "count"),
    ("banca_mestrado", "Banca de mestrado", "III", "III.2", "count"),
    ("banca_qualificacao", "Banca de exame de qualificação", "III", "III.7", "count"),
    ("banca_especializacao", "Banca de especialização/aperfeiçoamento", "III", "III.3", "count"),
    ("banca_graduacao", "Banca de TCC de graduação", "III", "III.4", "count"),
    ("banca_concurso", "Banca de concurso público", "III", "III.6", "count"),
    ("banca_livre_docencia", "Banca de livre-docência", "III", "III.1", "count"),
    ("banca_prof_titular", "Banca para professor titular", "III", "III.6", "count"),
    ("banca_avaliacao_cursos", "Banca de avaliação de cursos", "III", "III.11", "count"),
    ("banca_outra", "Outras bancas julgadoras", "III", "III.11", "count"),
    # Projetos
    ("proj_pesquisa_coord_sem_fin", "Projeto de pesquisa – coordenador, sem financiamento", "V", "V.1", "count"),
    ("proj_pesquisa_coord_fin_int", "Projeto de pesquisa – coordenador, financiamento interno (por ano)", "V", "V.2", "years"),
    ("proj_pesquisa_coord_fin_ext", "Projeto de pesquisa – coordenador, financiamento externo (por ano)", "V", "V.3", "years"),
    ("proj_pesquisa_part_sem_fin", "Projeto de pesquisa – integrante, sem financiamento (por ano)", "V", "V.4", "years"),
    ("proj_pesquisa_part_fin_int", "Projeto de pesquisa – integrante, financiamento interno (por ano)", "V", "V.5", "years"),
    ("proj_pesquisa_part_fin_ext", "Projeto de pesquisa – integrante, financiamento externo (por ano)", "V", "V.6", "years"),
    ("proj_extensao_coord", "Projeto de extensão – coordenador (por ano)", "IV", "IV.1", "years"),
    ("proj_extensao_part", "Projeto de extensão – integrante (por ano)", "IV", "IV.2", "years"),
    ("proj_ensino_coord", "Projeto de ensino – coordenador", "I", "I.6.a", "count"),
    ("proj_ensino_part", "Projeto de ensino – integrante", "I", "I.6.b", "count"),
    ("proj_outro", "Projeto de outra natureza", "V", None, "count"),
    # Produção bibliográfica
    ("artigo_internacional", "Artigo em periódico (internacional)", "VIII", "VIII.11", "count"),
    ("artigo_nacional", "Artigo em periódico (nacional)", "VIII", "VIII.12", "count"),
    ("livro_publicado", "Livro publicado", "VIII", "VIII.1", "count"),
    ("livro_organizado_internacional", "Livro organizado/editado (internacional)", "VIII", "VIII.9", "count"),
    ("livro_organizado_nacional", "Livro organizado/editado (nacional)", "VIII", "VIII.10", "count"),
    ("capitulo_internacional", "Capítulo de livro (internacional)", "VIII", "VIII.3", "count"),
    ("capitulo_nacional", "Capítulo de livro (nacional)", "VIII", "VIII.4", "count"),
    ("trabalho_evento_completo", "Trabalho completo/resumo expandido em evento nacional ou internacional", "VIII", "VIII.23", "count"),
    ("trabalho_evento_regional", "Trabalho completo/resumo expandido em evento regional/local", "VIII", "VIII.68", "count"),
    ("resumo_evento", "Resumo publicado em evento", "VIII", "VIII.24", "count"),
    ("texto_jornal", "Texto em jornal ou revista (imprensa)", "VIII", "VIII.18", "count"),
    ("prefacio_posfacio", "Prefácio/posfácio", "VIII", "VIII.69", "count"),
    ("traducao", "Tradução", "VIII", "VIII.17", "count"),
    ("outra_prod_bibliografica", "Outra produção bibliográfica", "VIII", None, "count"),
    # Produção técnica
    ("software_registrado", "Software com registro", "VIII", "VIII.63", "count"),
    ("software_sem_registro", "Software sem registro", "VIII", None, "count"),
    ("patente_concedida", "Patente concedida", "VIII", "VIII.36", "count"),
    ("patente_depositada", "Patente depositada", "VIII", "VIII.35", "count"),
    ("produto_tecnologico", "Produto tecnológico", "VIII", None, "count"),
    ("processo_tecnica", "Processo ou técnica", "VIII", None, "count"),
    ("trabalho_tecnico", "Trabalho técnico / consultoria / relatório técnico", "VIII", "VIII.19", "count"),
    ("apresentacao_internacional", "Apresentação de trabalho em evento (internacional)", "VIII", "VIII.26", "count"),
    ("apresentacao_nacional", "Apresentação de trabalho em evento (nacional)", "VIII", "VIII.27", "count"),
    ("apresentacao_conferencia", "Apresentação de trabalho – conferência/palestra", "VIII", "VIII.28", "count"),
    ("curso_curta_ministrado", "Curso de curta duração ministrado (a cada 3 h)", "IV", "IV.4", "hours3"),
    ("material_didatico", "Material didático ou instrucional", "VIII", "VIII.20", "count"),
    ("organizacao_evento", "Organização de evento", "VI", "VI.12", "count"),
    ("programa_radio_tv", "Programa de rádio ou TV / divulgação", "IV", "IV.9.b", "count"),
    ("editoracao", "Editoração", "VIII", "VIII.32", "count"),
    ("relatorio_pesquisa", "Relatório de pesquisa", "VIII", None, "count"),
    ("outra_prod_tecnica", "Outra produção técnica", "VIII", None, "count"),
    # Produção artística
    ("producao_artistica", "Produção artística/cultural", "VIII", None, "count"),
    # Prêmios
    ("premio_internacional", "Prêmio/título (internacional)", "VI", "VI.19.a", "count"),
    ("premio_nacional", "Prêmio/título (nacional)", "VI", "VI.19.b", "count"),
    # Atuação profissional
    ("ensino_graduacao", "Atividade de ensino – graduação (disciplinas)", "I", None, "count"),
    ("ensino_pos", "Atividade de ensino – pós-graduação (disciplinas)", "I", None, "count"),
    ("cargo_direcao", "Cargo de direção e administração (por ano)", "VI", None, "years"),
    ("conselho_comissao", "Conselho, comissão e consultoria (por ano)", "VI", "VI.10", "years"),
    ("revisor_periodico", "Revisor de periódico (por ano/revista)", "VIII", "VIII.66", "years"),
    ("corpo_editorial", "Membro de corpo editorial (por ano)", "VI", "VI.11", "years"),
    ("estagio_realizado", "Estágio realizado", "VII", None, "count"),
    ("treinamento_ministrado", "Treinamento ministrado", "IV", None, "count"),
]

CATEGORIAS_MAP = {c[0]: {"key": c[0], "label": c[1], "grupo": c[2], "item_padrao": c[3], "modo": c[4]} for c in CATEGORIAS}


def calcular_pontuacao(categorias_qtd, itens_por_key, mapeamento):
    """
    categorias_qtd: {categoria_key: {"qtd": float, "registros": [...]}}
    itens_por_key: {item_key: {"valor": float, "atividade": str, "grupo": str, ...}}
    mapeamento: {categoria_key: item_key or None}
    Retorna dict com linhas por categoria, totais por grupo e total geral.
    """
    linhas = []
    totais_grupo = {g: 0.0 for g in GRUPOS}
    total = 0.0
    for cat in CATEGORIAS:
        ckey = cat[0]
        info = categorias_qtd.get(ckey)
        qtd = float(info["qtd"]) if info else 0.0
        item_key = mapeamento.get(ckey, CATEGORIAS_MAP[ckey]["item_padrao"])
        item = itens_por_key.get(item_key) if item_key else None
        valor = float(item["valor"]) if item else 0.0
        pontos = qtd * valor if item else 0.0
        grupo = item["grupo"] if item else CATEGORIAS_MAP[ckey]["grupo"]
        if item:
            totais_grupo[grupo] += pontos
            total += pontos
        linhas.append({
            "categoria": ckey,
            "label": CATEGORIAS_MAP[ckey]["label"],
            "qtd": qtd,
            "item_key": item_key,
            "item_atividade": item["atividade"] if item else "— não pontua —",
            "valor": valor,
            "pontos": pontos,
            "grupo": grupo,
            "registros": info["registros"] if info else [],
        })
    return {"linhas": linhas, "totais_grupo": totais_grupo, "total": total}
