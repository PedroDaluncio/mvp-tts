import axios from 'axios'
import { useEffect, useRef, useState, type SubmitEvent } from 'react'
import ReferenceAudio from './ReferenceAudio'
import './App.css'

const kokoroVoices = [
  { id: 'pf_dora', name: 'Dora' },
  { id: 'pm_alex', name: 'Alex' },
  { id: 'pm_santa', name: 'Santa' },
]

function App() {
  const [text, setText] = useState('')
  const [provider, setProvider] = useState<'kokoro' | 'chatterbox'>('kokoro')
  const [kokoroVoice, setKokoroVoice] = useState(kokoroVoices[0].id)
  const [chatterboxVoice, setChatterboxVoice] = useState('default')
  const voice = provider === 'kokoro' ? kokoroVoice : chatterboxVoice
  const [reference, setReference] = useState<File | null>(null)
  const customVoice = provider === 'chatterbox' && voice === 'custom'
  const [isConverting, setIsConverting] = useState(false)
  const [audioUrl, setAudioUrl] = useState('')
  const [error, setError] = useState('')
  const activeRequest = useRef<AbortController | null>(null)
  const canConvert = Boolean(text.trim() && voice) && !isConverting && (!customVoice || Boolean(reference))

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
      let body: FormData | { text: string; provider: string; voice: string }
      if (customVoice && reference) {
        body = new FormData()
        body.append('text', text.trim())
        body.append('reference_audio', reference)
      } else {
        body = { text: text.trim(), provider, voice }
      }
      const { data } = await axios.post<Blob>(
        customVoice ? '/speech/chatterbox/custom' : '/speech',
        body,
        { baseURL: import.meta.env.VITE_API_BASE_URL, responseType: 'blob', signal: controller.signal },
      )
      if (data.type !== 'audio/wav' || !data.size) {
        throw new Error('Resposta de áudio inválida')
      }
      setAudioUrl(URL.createObjectURL(data))
    } catch (cause) {
      if (!controller.signal.aborted) {
        setError(customVoice && axios.isAxiosError(cause) && cause.response?.status === 422
          ? 'Escolha um áudio de referência válido com pelo menos um segundo de fala.'
          : 'Não foi possível gerar o áudio. Tente novamente.')
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
          onChange={(event) => setProvider(event.target.value === 'chatterbox' ? 'chatterbox' : 'kokoro')}
        >
          <option value="kokoro">Kokoro</option>
          <option value="chatterbox">Chatterbox</option>
        </select>
        <label className="select-label" htmlFor="speech-voice">Voz</label>
        <select
          id="speech-voice"
          name="voice"
          required
          value={voice}
          disabled={isConverting}
          onChange={(event) => {
            if (provider === 'chatterbox') setChatterboxVoice(event.target.value)
            else setKokoroVoice(event.target.value)
          }}
        >
          {provider === 'chatterbox' ? (
            <>
              <option value="default">Voz padrão</option>
              <option value="custom">Voz personalizada</option>
            </>
          ) : (
            <>
              <option value="">Selecione uma voz</option>
              {kokoroVoices.map(({ id, name }) => (
                <option key={id} value={id}>{name}</option>
              ))}
            </>
          )}
        </select>
        {customVoice && <ReferenceAudio file={reference} setFile={setReference} disabled={isConverting} />}
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
