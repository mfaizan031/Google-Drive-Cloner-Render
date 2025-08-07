import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button.jsx'
import { Input } from '@/components/ui/input.jsx'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.jsx'
import { Alert, AlertDescription } from '@/components/ui/alert.jsx'
import { Progress } from '@/components/ui/progress.jsx'
import { Badge } from '@/components/ui/badge.jsx'
import { Loader2, Download, FolderOpen, FileText, CheckCircle, AlertCircle } from 'lucide-react'
import './App.css'

// Use environment variable for API_BASE
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000/api'

function App() {
  const [driveUrl, setDriveUrl] = useState('')
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [loading, setLoading] = useState(false)
  const [fileInfo, setFileInfo] = useState(null)
  const [cloneProgress, setCloneProgress] = useState(null)
  const [taskId, setTaskId] = useState(null)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  // Check authentication status on load
  useEffect(() => {
    checkAuthStatus()
  }, [])

  // Poll for progress updates
  useEffect(() => {
    let interval
    if (taskId && cloneProgress?.status !== 'completed' && cloneProgress?.status !== 'failed') {
      interval = setInterval(async () => {
        try {
          const response = await fetch(`${API_BASE}/progress/${taskId}`)
          if (response.ok) {
            const progress = await response.json()
            setCloneProgress(progress)
            
            if (progress.status === 'completed') {
              setSuccess(`Successfully cloned "${progress.result?.name}"!`)
              clearInterval(interval)
            } else if (progress.status === 'failed') {
              setError('Clone operation failed. Please try again.')
              clearInterval(interval)
            }
          }
        } catch (err) {
          console.error('Error fetching progress:', err)
        }
      }, 1000)
    }
    
    return () => {
      if (interval) clearInterval(interval)
    }
  }, [taskId, cloneProgress?.status])

  const checkAuthStatus = async () => {
    try {
      const response = await fetch(`${API_BASE}/auth/status`)
      if (response.ok) {
        const data = await response.json()
        setIsAuthenticated(data.authenticated)
      }
    } catch (err) {
      console.error('Error checking auth status:', err)
    }
  }

  const handleGoogleLogin = async () => {
    try {
      const response = await fetch(`${API_BASE}/auth/login`)
      if (response.ok) {
        const data = await response.json()
        window.location.href = data.auth_url
      }
    } catch (err) {
      setError('Failed to initiate Google login')
    }
  }

  const parseUrl = async () => {
    if (!driveUrl.trim()) {
      setError('Please enter a Google Drive URL')
      return
    }

    setLoading(true)
    setError('')
    setFileInfo(null)

    try {
      const response = await fetch(`${API_BASE}/parse-url`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ url: driveUrl }),
        credentials: 'include'
      })

      if (response.ok) {
        const data = await response.json()
        setFileInfo(data)
      } else {
        const errorData = await response.json()
        setError(errorData.error || 'Failed to parse URL')
      }
    } catch (err) {
      setError('Network error. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const startClone = async () => {
    if (!fileInfo) return

    setLoading(true)
    setError('')
    setSuccess('')
    setCloneProgress(null)

    try {
      const response = await fetch(`${API_BASE}/clone`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ file_id: fileInfo.id }),
        credentials: 'include'
      })

      if (response.ok) {
        const data = await response.json()
        setTaskId(data.task_id)
        setCloneProgress({ status: 'starting', percentage: 0 })
      } else {
        const errorData = await response.json()
        setError(errorData.error || 'Failed to start clone')
      }
    } catch (err) {
      setError('Network error. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const resetForm = () => {
    setDriveUrl('')
    setFileInfo(null)
    setCloneProgress(null)
    setTaskId(null)
    setError('')
    setSuccess('')
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-4">
      <div className="max-w-2xl mx-auto">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-2">
            Google Drive Clone Tool
          </h1>
          <p className="text-gray-600">
            Clone any Google Drive folder or file to your own Drive
          </p>
        </div>

        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Download className="w-5 h-5" />
              Clone Drive Content
            </CardTitle>
            <CardDescription>
              Enter a Google Drive share URL to clone files and folders
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {!isAuthenticated ? (
              <div className="text-center py-8">
                <p className="text-gray-600 mb-4">
                  Sign in with Google to start cloning Drive content
                </p>
                <Button onClick={handleGoogleLogin} className="bg-blue-600 hover:bg-blue-700">
                  <svg className="w-4 h-4 mr-2" viewBox="0 0 24 24">
                    <path fill="currentColor" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                    <path fill="currentColor" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                    <path fill="currentColor" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                    <path fill="currentColor" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                  </svg>
                  Sign in with Google
                </Button>
              </div>
            ) : (
              <>
                <div className="flex gap-2">
                  <Input
                    placeholder="https://drive.google.com/drive/folders/..."
                    value={driveUrl}
                    onChange={(e) => setDriveUrl(e.target.value)}
                    className="flex-1"
                  />
                  <Button 
                    onClick={parseUrl} 
                    disabled={loading || !driveUrl.trim()}
                    className="bg-blue-600 hover:bg-blue-700"
                  >
                    {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Parse'}
                  </Button>
                </div>

                {error && (
                  <Alert className="border-red-200 bg-red-50">
                    <AlertCircle className="w-4 h-4 text-red-600" />
                    <AlertDescription className="text-red-800">
                      {error}
                    </AlertDescription>
                  </Alert>
                )}

                {success && (
                  <Alert className="border-green-200 bg-green-50">
                    <CheckCircle className="w-4 h-4 text-green-600" />
                    <AlertDescription className="text-green-800">
                      {success}
                    </AlertDescription>
                  </Alert>
                )}

                {fileInfo && (
                  <Card className="bg-gray-50">
                    <CardContent className="pt-6">
                      <div className="flex items-start gap-3">
                        {fileInfo.type === 'folder' ? (
                          <FolderOpen className="w-6 h-6 text-blue-600 mt-1" />
                        ) : (
                          <FileText className="w-6 h-6 text-gray-600 mt-1" />
                        )}
                        <div className="flex-1">
                          <h3 className="font-semibold text-gray-900">{fileInfo.name}</h3>
                          <div className="flex gap-2 mt-2">
                            <Badge variant="secondary">
                              {fileInfo.type === 'folder' ? 'Folder' : 'File'}
                            </Badge>
                            {fileInfo.item_count && (
                              <Badge variant="outline">
                                {fileInfo.item_count} items
                              </Badge>
                            )}
                            {fileInfo.size !== 'Unknown' && (
                              <Badge variant="outline">
                                {fileInfo.size} bytes
                              </Badge>
                            )}
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                )}

                {cloneProgress && (
                  <Card className="bg-blue-50">
                    <CardContent className="pt-6">
                      <div className="space-y-3">
                        <div className="flex justify-between items-center">
                          <span className="font-medium">Clone Progress</span>
                          <Badge 
                            variant={
                              cloneProgress.status === 'completed' ? 'default' :
                              cloneProgress.status === 'failed' ? 'destructive' : 'secondary'
                            }
                          >
                            {cloneProgress.status}
                          </Badge>
                        </div>
                        
                        <Progress value={cloneProgress.percentage || 0} className="w-full" />
                        
                        <div className="text-sm text-gray-600">
                          {cloneProgress.current_file && (
                            <p>Processing: {cloneProgress.current_file}</p>
                          )}
                          <p>
                            {cloneProgress.completed || 0} of {cloneProgress.total || 0} items
                          </p>
                        </div>

                        {cloneProgress.errors && cloneProgress.errors.length > 0 && (
                          <div className="text-sm text-red-600">
                            <p className="font-medium">Errors:</p>
                            {cloneProgress.errors.map((error, index) => (
                              <p key={index}>• {error}</p>
                            ))}
                          </div>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                )}

                <div className="flex gap-2">
                  {fileInfo && !cloneProgress && (
                    <Button 
                      onClick={startClone} 
                      disabled={loading}
                      className="flex-1 bg-green-600 hover:bg-green-700"
                    >
                      {loading ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
                      Start Clone
                    </Button>
                  )}
                  
                  {(fileInfo || cloneProgress) && (
                    <Button 
                      onClick={resetForm} 
                      variant="outline"
                      className="flex-1"
                    >
                      Reset
                    </Button>
                  )}
                </div>
              </>
            )}
          </CardContent>
        </Card>

        <div className="text-center text-sm text-gray-500">
          <p>
            This tool creates copies of publicly accessible Google Drive content.
            <br />
            Make sure you have permission to access the content you want to clone.
          </p>
        </div>
      </div>
    </div>
  )
}

export default App


