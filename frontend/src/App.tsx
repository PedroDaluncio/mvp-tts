import axios from 'axios'
import { useEffect, useRef, useState, type SubmitEvent } from 'react'
import './App.css'

const voicesByProvider = {
  kokoro: [
    { id: 'pf_dora', name: 'Dora' },
    { id: 'pm_alex', name: 'Alex' },
    { id: 'pm_santa', name: 'Santa' },
  ],
  edge: [
    { id: 'pt-BR-FranciscaNeural', name: 'Francisca' },
    { id: 'pt-BR-AntonioNeural', name: 'Antônio' },
  ],
}

type Provider = keyof typeof voicesByProvider

function App() {
  const [text, setText] = useState('')
  const [provider, setProvider] = useState<Provider>('kokoro')
  const [voice, setVoice] = useState(voicesByProvider.kokoro[0].id)
  const [isConverting, setIsConverting] = useState(false)
  const [audioUrl, setAudioUrl] = useState('')
  const [error, setError] = useState('')
  const activeRequest = useRef<AbortController | null>(null)
  const canConvert = Boolean(text.trim() && voice) && !isConverting

  useEffect(() => {
    const cancel = () => activeRequest.current?.abort()
    window.addEventListener('pagehide', cancel)
    return () => {
      window.removeEventListener('pagehide', cancel)
      cancel()
    }
  }, [])

  useEffect(() => {
    return () => {
      if (audioUrl) URL.revokeObjectURL(audioUrl)
    }
  }, [audioUrl])

  async function convert(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!canConvert || activeRequest.current) return

    const controller = new AbortController()
    activeRequest.current = controller
    setIsConverting(true)
    setError('')
    setAudioUrl('')
    try {
      const { data } = await axios.post<Blob>(
        '/speech',
        { text: text.trim(), provider, voice },
        { baseURL: import.meta.env.VITE_API_BASE_URL, responseType: 'blob', signal: controller.signal },
      )
      if (data.type !== 'audio/wav' || !data.size) {
        throw new Error('Resposta de áudio inválida')
      }
      setAudioUrl(URL.createObjectURL(data))
    } catch {
      if (!controller.signal.aborted) {
        setError('Não foi possível gerar o áudio. Tente novamente.')
      }
    } finally {
      activeRequest.current = null
      setIsConverting(false)
    }
  }

  return (
    <main className="editor">
      <form onSubmit={convert}>
        <h1><label htmlFor="speech-text">Texto para narração</label></h1>
        <textarea
          id="speech-text"
          name="text"
          rows={8}
          placeholder="Digite ou cole seu texto aqui…"
          required
          value={text}
          onChange={(event) => setText(event.target.value)}
        />
        <label className="select-label" htmlFor="speech-provider">Modelo</label>
        <select
          id="speech-provider"
          name="provider"
          value={provider}
          disabled={isConverting}
          onChange={(event) => {
            const nextProvider = event.target.value as Provider
            setProvider(nextProvider)
            setVoice(voicesByProvider[nextProvider][0].id)
          }}
        >
          <option value="kokoro">Kokoro (local)</option>
          <option value="edge">Microsoft Edge TTS (online)</option>
        </select>
        <label className="select-label" htmlFor="speech-voice">Voz</label>
        <select
          id="speech-voice"
          name="voice"
          required
          value={voice}
          disabled={isConverting}
          onChange={(event) => setVoice(event.target.value)}
        >
          <option value="">Selecione uma voz</option>
          {voicesByProvider[provider].map(({ id, name }) => (
            <option key={id} value={id}>{name}</option>
          ))}
        </select>
        <button type="submit" disabled={!canConvert}>
          {isConverting ? 'Gerando áudio…' : 'Converter texto em voz'}
        </button>
      </form>
      {error && <p role="alert">{error}</p>}
      {audioUrl && <audio controls src={audioUrl} aria-label="Narração gerada" />}
    </main>
  )
}

export default App
