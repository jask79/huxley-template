// Package logging provides structured JSON logging to stderr for launchd daemons.
package logging

import (
	"encoding/json"
	"fmt"
	"os"
	"time"
)

// Level represents log severity.
type Level string

const (
	LevelInfo  Level = "INFO"
	LevelDebug Level = "DEBUG"
	LevelWarn  Level = "WARN"
	LevelError Level = "ERROR"
)

// Logger writes structured JSON entries to stderr.
type Logger struct {
	daemon string
}

// New creates a Logger tagged with the daemon name.
func New(daemon string) *Logger {
	return &Logger{daemon: daemon}
}

type entry struct {
	Time    string `json:"time"`
	Daemon  string `json:"daemon"`
	Level   Level  `json:"level"`
	Message string `json:"msg"`
}

func (l *Logger) log(level Level, msg string) {
	e := entry{
		Time:    time.Now().UTC().Format(time.RFC3339),
		Daemon:  l.daemon,
		Level:   level,
		Message: msg,
	}
	b, err := json.Marshal(e)
	if err != nil {
		fmt.Fprintf(os.Stderr, `{"daemon":%q,"level":"ERROR","msg":"log marshal failed"}`+"\n", l.daemon)
		return
	}
	fmt.Fprintf(os.Stderr, "%s\n", b)
}

func (l *Logger) Infof(format string, args ...any) {
	l.log(LevelInfo, fmt.Sprintf(format, args...))
}

func (l *Logger) Debugf(format string, args ...any) {
	l.log(LevelDebug, fmt.Sprintf(format, args...))
}

func (l *Logger) Warnf(format string, args ...any) {
	l.log(LevelWarn, fmt.Sprintf(format, args...))
}

func (l *Logger) Errorf(format string, args ...any) {
	l.log(LevelError, fmt.Sprintf(format, args...))
}
