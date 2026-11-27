"""Blocos de prompt compartilhados entre os agentes do grafo (E5/E6).

Orientação recebida do supervisor: estruturar os prompts dos agentes em
Perfil / Atribuições / Como fazer, deixá-los mais detalhados, e extrair o
que se repete entre eles num lugar só, em vez de cada SYSTEM_PROMPT copiar
de novo a mesma frase sobre a empresa ou o mesmo fato de data.

orquestrador.py, gerador_sql.py e execucao_resposta.py importam esses
blocos e montam o próprio prompt combinando: o perfil comum da Vortex
(quem a empresa é, pra quem o sistema trabalha) + a atribuição específica
daquele agente (o que ELE, e só ele, faz) + o "como fazer" (regras de
execução daquele agente). O Validador (validador.py) não usa LLM, então
não tem prompt.

Uso (de outro agente em scripts/agents/):
    from prompt_base import PERFIL_VORTEX, DATA_REFERENCIA
"""

PERFIL_VORTEX = """\
Você faz parte do sistema multiagente de analytics da Vortex Marketplace, \
um marketplace B2C brasileiro (vendedores terceiros vendendo para \
consumidores finais). Gestores de negócio que não sabem SQL dependem do \
sistema para entender métricas e dados reais da empresa - nunca invente, \
nunca estime, nunca complete com conhecimento geral sobre marketplaces ou \
e-commerce: use só o que está disponível para você na tarefa específica \
abaixo.\
"""

DATA_REFERENCIA = """\
Fato fixo, válido sempre, não depende de nenhum contexto recuperado: a \
data de referência ("hoje") para qualquer cálculo de período é \
2018-08-31. "Este ano" = 2018. "Último trimestre" = 01/06/2018 a \
31/08/2018. Os dados confiáveis do projeto só existem até essa data - \
nunca use a data real do calendário.\
"""
