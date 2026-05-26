import { useState, useCallback } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import type { EntityType } from '../types'

function applyPhoneMask(value: string): string {
  const digits = value.replace(/\D/g, '')
  if (digits.length <= 2) return digits.length ? `(${digits}` : ''
  if (digits.length <= 6) return `(${digits.slice(0,2)}) ${digits.slice(2)}`
  if (digits.length <= 10) return `(${digits.slice(0,2)}) ${digits.slice(2,6)}-${digits.slice(6)}`
  return `(${digits.slice(0,2)}) ${digits.slice(2,7)}-${digits.slice(7,11)}`
}

function applyMask(value: string, type: EntityType): string {
  if (type === 'apelido') return value
  const digits = value.replace(/\D/g, '')
  if (type === 'cpf') {
    if (digits.length <= 3) return digits
    if (digits.length <= 6) return `${digits.slice(0,3)}.${digits.slice(3)}`
    if (digits.length <= 9) return `${digits.slice(0,3)}.${digits.slice(3,6)}.${digits.slice(6)}`
    return `${digits.slice(0,3)}.${digits.slice(3,6)}.${digits.slice(6,9)}-${digits.slice(9,11)}`
  } else {
    if (digits.length <= 2) return digits
    if (digits.length <= 5) return `${digits.slice(0,2)}.${digits.slice(2)}`
    if (digits.length <= 8) return `${digits.slice(0,2)}.${digits.slice(2,5)}.${digits.slice(5)}`
    if (digits.length <= 12) return `${digits.slice(0,2)}.${digits.slice(2,5)}.${digits.slice(5,8)}/${digits.slice(8)}`
    return `${digits.slice(0,2)}.${digits.slice(2,5)}.${digits.slice(5,8)}/${digits.slice(8,12)}-${digits.slice(12,14)}`
  }
}

const ENTITY_TYPES: { value: EntityType; label: string; sublabel: string }[] = [
  { value: 'cpf',     label: 'CPF',     sublabel: 'Pessoa Física' },
  { value: 'cnpj',    label: 'CNPJ',    sublabel: 'Pessoa Jurídica' },
  { value: 'apelido', label: 'Apelido', sublabel: 'Sem documento' },
]

export default function NewInvestigation() {
  const navigate = useNavigate()
  const [entityType, setEntityType] = useState<EntityType>('cpf')
  const [entityName, setEntityName] = useState('')
  const [entityId, setEntityId] = useState('')
  const [email, setEmail] = useState('')
  const [nickname, setNickname] = useState('')
  const [phone, setPhone] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleEntityIdChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const masked = applyMask(e.target.value, entityType)
    setEntityId(masked)
  }, [entityType])

  const handleEntityTypeChange = (type: EntityType) => {
    setEntityType(type)
    setEntityId('')
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)

    if (entityType !== 'apelido') {
      const digits = entityId.replace(/\D/g, '')
      const expectedLen = entityType === 'cpf' ? 11 : 14
      if (digits.length > 0 && digits.length !== expectedLen) {
        setError(`${entityType.toUpperCase()} incompleto — informe ${expectedLen} dígitos ou deixe em branco.`)
        setLoading(false)
        return
      }
    }

    try {
      const inv = await api.createInvestigation({
        entity_name: entityName.trim(),
        entity_type: entityType,
        entity_id: entityType !== 'apelido' && entityId.replace(/\D/g, '').length > 0 ? entityId.replace(/\D/g, '') : null,
        email: email.trim() || undefined,
        nickname: nickname.trim() || null,
        phone: phone.replace(/\D/g, '') || null,
      })
      navigate(`/investigacoes/${inv.id}/relatorio`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao criar investigação')
      setLoading(false)
    }
  }

  const digits = entityId.replace(/\D/g, '')
  const expectedLen = entityType === 'cpf' ? 11 : 14
  const isValid =
    entityName.trim().length >= 2 &&
    (entityType === 'apelido' ||
      digits.length === 0 ||
      digits.length === expectedLen)

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 shadow-sm">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 py-4 flex items-center gap-4">
          <Link to="/dashboard" className="text-gray-400 hover:text-gray-600 transition-colors">
            ← Voltar
          </Link>
          <div>
            <h1 className="text-xl font-bold text-gray-900">Nova Investigação</h1>
            <p className="text-sm text-gray-500">Preencha os dados do sujeito a ser investigado</p>
          </div>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 sm:px-6 py-10">
        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-8">
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Entity Type Toggle */}
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-2">
                Tipo de Busca
              </label>
              <div className="flex gap-0 rounded-lg border border-gray-200 overflow-hidden w-fit">
                {ENTITY_TYPES.map(({ value, label, sublabel }) => (
                  <button
                    key={value}
                    type="button"
                    onClick={() => handleEntityTypeChange(value)}
                    className={`px-6 py-2.5 text-sm font-semibold transition-colors ${
                      entityType === value
                        ? 'bg-blue-600 text-white'
                        : 'bg-white text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    {label}
                    <span className="ml-1.5 text-xs font-normal opacity-70">({sublabel})</span>
                  </button>
                ))}
              </div>
              {entityType === 'apelido' && (
                <p className="text-xs text-amber-600 mt-2 bg-amber-50 border border-amber-100 rounded-lg px-3 py-2">
                  Modo apelido: busca apenas em mídias negativas, listas restritivas e redes sociais.
                  Consulta CNPJ/CPF não será realizada.
                </p>
              )}
            </div>

            {/* Name / Apelido */}
            <div>
              <label htmlFor="name" className="block text-sm font-semibold text-gray-700 mb-1.5">
                {entityType === 'cnpj' ? 'Razão Social' : entityType === 'apelido' ? 'Apelido / Nome Conhecido' : 'Nome Completo'}
                <span className="text-red-500 ml-1">*</span>
              </label>
              <input
                id="name"
                type="text"
                value={entityName}
                onChange={(e) => setEntityName(e.target.value)}
                placeholder={
                  entityType === 'cnpj' ? 'Ex: Empresa Exemplo Ltda' :
                  entityType === 'apelido' ? 'Ex: Marcola, Zé Pelintra, Big Boss' :
                  'Ex: João da Silva Santos'
                }
                className="w-full border border-gray-300 rounded-lg px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors"
                required
              />
            </div>

            {/* Entity ID — hidden in apelido mode */}
            {entityType !== 'apelido' && (
              <div>
                <label htmlFor="entity-id" className="block text-sm font-semibold text-gray-700 mb-1.5">
                  {entityType === 'cpf' ? 'CPF' : 'CNPJ'}
                  <span className="text-gray-400 font-normal ml-2 text-xs">(opcional)</span>
                </label>
                <input
                  id="entity-id"
                  type="text"
                  value={entityId}
                  onChange={handleEntityIdChange}
                  placeholder={entityType === 'cpf' ? '000.000.000-00' : '00.000.000/0000-00'}
                  maxLength={entityType === 'cpf' ? 14 : 18}
                  className="w-full border border-gray-300 rounded-lg px-4 py-3 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors"
                />
                <p className="text-xs text-gray-400 mt-1">
                  {entityType === 'cpf' ? '11 dígitos' : '14 dígitos'}
                </p>
              </div>
            )}

            {/* Email */}
            <div>
              <label htmlFor="email" className="block text-sm font-semibold text-gray-700 mb-1.5">
                E-mail
                <span className="text-gray-400 font-normal ml-2 text-xs">(opcional — reduz falsos positivos)</span>
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="exemplo@dominio.com.br"
                className="w-full border border-gray-300 rounded-lg px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors"
              />
              <p className="text-xs text-gray-400 mt-1">
                Usado para verificação de vazamentos de dados (HIBP) e mapeamento de redes sociais
              </p>
            </div>

            {/* Nickname */}
            {entityType !== 'apelido' && (
              <div>
                <label htmlFor="nickname" className="block text-sm font-semibold text-gray-700 mb-1.5">
                  Apelido / Nome Conhecido
                  <span className="text-gray-400 font-normal ml-2 text-xs">(opcional)</span>
                </label>
                <input
                  id="nickname"
                  type="text"
                  value={nickname}
                  onChange={(e) => setNickname(e.target.value)}
                  placeholder="Ex: Zé da Roça, Dr. Silva"
                  className="w-full border border-gray-300 rounded-lg px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors"
                />
                <p className="text-xs text-gray-400 mt-1">
                  Amplia a busca em mídias negativas e redes sociais
                </p>
              </div>
            )}

            {/* Phone */}
            <div>
              <label htmlFor="phone" className="block text-sm font-semibold text-gray-700 mb-1.5">
                Telefone
                <span className="text-gray-400 font-normal ml-2 text-xs">(opcional)</span>
              </label>
              <input
                id="phone"
                type="text"
                value={phone}
                onChange={(e) => setPhone(applyPhoneMask(e.target.value))}
                placeholder="(00) 00000-0000"
                maxLength={16}
                className="w-full border border-gray-300 rounded-lg px-4 py-3 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors"
              />
            </div>

            {error && (
              <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3">
                <p className="text-sm text-red-700">{error}</p>
              </div>
            )}

            {/* Info box */}
            <div className="bg-blue-50 border border-blue-100 rounded-lg px-4 py-3">
              <p className="text-xs text-blue-700 leading-relaxed">
                <strong>Fontes consultadas:</strong>{' '}
                {entityType === 'cnpj'
                  ? 'Receita Federal (CNPJ), Mídias Negativas, Listas PEP/OFAC e Redes Sociais.'
                  : entityType === 'apelido'
                  ? 'Mídias Negativas (Google/DuckDuckGo), Listas PEP/OFAC e Redes Sociais.'
                  : 'Mídias Negativas, Listas PEP/OFAC, Redes Sociais (LinkedIn, Instagram, Twitter, TikTok) e Verificação de Vazamentos (HaveIBeenPwned).'}
                {' '}A investigação é executada em paralelo e pode levar até 2 minutos.
              </p>
            </div>

            <button
              type="submit"
              disabled={!isValid || loading}
              className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-bold py-3.5 rounded-xl transition-colors shadow-sm text-sm"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
                  Iniciando investigação...
                </span>
              ) : (
                'Iniciar Investigação'
              )}
            </button>
          </form>
        </div>
      </main>
    </div>
  )
}
