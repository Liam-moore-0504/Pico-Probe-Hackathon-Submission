import React, {Component} from 'react'
import {createRoot} from 'react-dom/client'
import App from './App'
import './styles.css'
import './governance.css'
class ErrorBoundary extends Component {
  constructor(props){super(props);this.state={error:null}}
  static getDerivedStateFromError(error){return {error}}
  componentDidCatch(error,details){console.error('Pico Probe interface error',error,details)}
  render(){
    if(this.state.error)return <main className="crashPage"><div><span className="eyebrow">INTERFACE RECOVERY</span><h1>Pico Probe hit an unexpected error.</h1><p>Your investigation is still saved. Reload the interface to continue.</p><button className="primary" onClick={()=>location.reload()}>Reload Pico Probe</button><details><summary>Technical details</summary><pre>{this.state.error.message}</pre></details></div></main>
    return this.props.children
  }
}

createRoot(document.getElementById('root')).render(<React.StrictMode><ErrorBoundary><App/></ErrorBoundary></React.StrictMode>)
