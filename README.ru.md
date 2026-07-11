# Интеграция SIM800C для Home Assistant

[English](README.md) | **Русский**

Интеграция Home Assistant для GSM-модуля SIM800C, подключённого по USB/Serial.

Поддерживает **SMS** (приём и отправку) и **голосовые звонки** (дозвон-оповещения / уведомления о пропущенных).

## Возможности

- Отправка SMS через сервис `sim800c.send_sms`
- Приём SMS: `sensor.sim800c_last_sms` (+ `sensor.sim800c_last_sms_sender` с номером отправителя) и событие `sim800c_incoming_sms`, с автоматическим декодированием GSM/UCS2
- Голосовые звонки через сервис `sim800c.call`, с автосбросом и отчётом «ответили / не ответили» (звук не проигрывается)
- Проигрывание готового аудиоклипа **AMR-NB** в звонок через сервис `sim800c.call_and_play`, чтобы собеседник его услышал, с автосбросом
- Ответ на входящий звонок, запись собеседника и **распознавание речи** через локальный Whisper-совместимый STT-сервис (GigaAM) сервисом `sim800c.answer_and_record`; результат — в `sensor.sim800c_last_recording` и событии `sim800c_call_recorded`
- Сброс активного звонка через сервис `sim800c.hang_up`
- Определение входящих звонков через `binary_sensor.sim800c_incoming_call` (с номером звонящего) и событие `sim800c_incoming_call`
- Актуальное состояние звонка в `sensor.sim800c_call_state` (`idle` / `dialing` / `ringing` / `active` / `incoming`)
- Полная поддержка Unicode (кириллица, китайский, арабский и т.д.) с автоматическим выбором кодировки GSM 7-bit / UCS2
- Настройка через UI (config flow) — без правки YAML
- Диагностические сенсоры уровня сигнала и регистрации в сети
- Сериализованный доступ к модему — отправки SMS и звонки никогда не конфликтуют на последовательном порту
- Работает с GSM-модулями SIM800C, подключёнными по USB или serial

## Установка

### Ручная установка

1. Скопируйте каталог `custom_components/sim800c` в каталог `custom_components` вашего Home Assistant.
2. Перезапустите Home Assistant.

### Установка через HACS

1. Добавьте этот репозиторий как пользовательский (custom repository) в HACS.
2. Найдите «SIM800C» и установите.
3. Перезапустите Home Assistant.

## Настройка

Настройка выполняется полностью через UI Home Assistant (config flow) — правка YAML не требуется.

1. Откройте **Настройки → Устройства и службы → Добавить интеграцию**.
2. Найдите **SIM800C** и выберите её.
3. Укажите **путь к устройству** модема (например, `/dev/ttyUSB0`) и **скорость порта** (по умолчанию `9600`).
4. Home Assistant подключится к модему и проверит его регистрацию в сети перед созданием записи.

### Как найти путь к устройству

В Linux модуль SIM800C обычно появляется как `/dev/ttyUSB0` или `/dev/ttyUSB1`. Доступные последовательные устройства можно посмотреть командой:

```bash
ls -l /dev/ttyUSB*
```

Либо используйте вкладку «Оборудование» в Настройки → Система → Оборудование внутри Home Assistant, чтобы найти путь после подключения модуля.

## Использование

### Отправка SMS

Используйте сервис `sim800c.send_sms` для отправки сообщения:

```yaml
service: sim800c.send_sms
data:
  target: "+79990001122"
  message: "Hello from Home Assistant!"
```

`target` принимает как один номер, так и список номеров. Необязательное поле `force_unicode` принудительно включает кодировку UCS2, даже если сообщение поместилось бы в GSM 7-bit:

| Поле | Обязательно | Описание |
| --- | --- | --- |
| `target` | Да | Номер(а) телефона в международном формате (`+7...`). Строка или список. |
| `message` | Да | Текст сообщения. Кириллица и другой Unicode поддерживаются. |
| `force_unicode` | Нет | Всегда отправлять как UCS2, даже если текст помещается в GSM 7-bit. По умолчанию `false`. |

### Несколько получателей

Можно отправить на несколько номеров:

```yaml
service: sim800c.send_sms
data:
  target:
    - "+79990001122"
    - "+79990003344"
  message: "Alert: Motion detected!"
```

### Пример автоматизации

```yaml
automation:
  - alias: "Send SMS on alarm trigger"
    triggers:
      - trigger: state
        entity_id: alarm_control_panel.home
        to: "triggered"
    actions:
      - action: sim800c.send_sms
        data:
          target: "+79990001122"
          message: "⚠️ Alarm triggered at home!"
```

## Поддержка Unicode

Сообщения автоматически кодируются в GSM 7-bit, когда текст помещается в этот набор символов, и в UCS2 в остальных случаях — так что можно писать на любом языке без настройки, включая:

- Кириллицу (русский, украинский, болгарский и т.д.)
- Китайский
- Арабский
- Греческий
- И другие!

Пример:

```yaml
service: sim800c.send_sms
data:
  target: "+79990001122"
  message: "Привет! Это сообщение на русском языке."
```

Установите `force_unicode: true`, если нужно принудительно закодировать в UCS2 сообщение, которое иначе ушло бы как GSM 7-bit.

## Приём SMS

Интеграция в фоне следит за принятыми сообщениями. При приходе SMS происходит два события:

- `sensor.sim800c_last_sms` обновляется на текст сообщения. В его атрибутах — полный `text`, `sender` и `timestamp`.
- Срабатывает **событие** `sim800c_incoming_sms` с `{"sender": "...", "text": "...", "timestamp": "..."}`.

Тело сообщения декодируется автоматически как в GSM 7-bit, так и в Unicode (UCS2 — кириллица, эмодзи и т.д.).

Пример автоматизации на принятое SMS:

```yaml
automation:
  - alias: "Forward incoming SMS to my phone"
    triggers:
      - trigger: event
        event_type: sim800c_incoming_sms
    actions:
      - action: notify.mobile_app_phone
        data:
          title: "📩 SMS from {{ trigger.event.data.sender }}"
          message: "{{ trigger.event.data.text }}"
```

Реагировать только на сообщения от конкретного отправителя (например, от блока ворот/сигнализации):

```yaml
automation:
  - alias: "Balance alert"
    triggers:
      - trigger: event
        event_type: sim800c_incoming_sms
    conditions:
      - condition: template
        value_template: "{{ 'balance' in trigger.event.data.text | lower }}"
    actions:
      - action: persistent_notification.create
        data:
          title: "SIM balance"
          message: "{{ trigger.event.data.text }}"
```

> **Примечания:**
> - После прочтения сообщения и срабатывания события оно **удаляется с модема**, чтобы избежать дублей событий и не переполнять ограниченную память SIM.
> - Входящие SMS обнаруживаются опросом каждые несколько секунд (не мгновенно).
> - Длинные (многочастные) сообщения приходят **отдельными событиями**, по одному на часть — интеграция не склеивает составные SMS.

## Голосовые звонки

Интеграция умеет совершать и наблюдать голосовые звонки. Звук не проигрывается и не записывается — это для **дозвон-оповещений** и **уведомлений о пропущенных**, а также чтобы понимать, ответили ли на звонок.

### Совершить звонок

Используйте сервис `sim800c.call`:

```yaml
service: sim800c.call
data:
  target: "+79990001122"
  ring_duration: 30   # необязательно, сколько секунд звонить до автосброса (1–120)
```

| Поле | Обязательно | Описание |
| --- | --- | --- |
| `target` | Да | Номер телефона в международном формате (`+7...`). |
| `ring_duration` | Нет | Сколько секунд звонить до сброса (1–120, по умолчанию `30`). Звонок также завершается раньше, если собеседник ответил или положил трубку. |

Сервис **возвращает ответ**, ответили ли на звонок:

```yaml
# В скрипте/автоматизации через response variables:
- action: sim800c.call
  data:
    target: "+79990001122"
  response_variable: call_result
- if: "{{ call_result.answered }}"
  then:
    - action: notify.mobile_app
      data:
        message: "They picked up!"
```

`call_result` выглядит как `{"answered": true, "state": "answered"}`. `state` — одно из `answered`, `no_answer` (прозвонил и автосброс) или `ended` (собеседник сбросил / отклонил до ответа).

### Проигрывание аудио в звонок

В отличие от `sim800c.call`, сервис `sim800c.call_and_play` проигрывает готовый аудиоклип **в звонок**, так что тот, кому вы звоните, действительно **его слышит**. Клип загружается в модем, набирается номер, и после ответа собеседника клип проигрывается в исходящий канал звонка; затем звонок автоматически сбрасывается.

```yaml
service: sim800c.call_and_play
data:
  target: "+79990001122"
  audio_file: "/media/sim800c/alert.amr"
  duration: 5          # необязательно, известная длительность клипа в секундах
  ring_duration: 30    # необязательно, сколько секунд звонить до отказа (1–120)
  volume: 90           # необязательно, 0–100 (по умолчанию 90)
```

| Поле | Обязательно | Описание |
| --- | --- | --- |
| `target` | Да | Номер телефона в международном формате (`+7...`). |
| `audio_file` | Да | Путь к локальному файлу **AMR-NB**, доступному Home Assistant. Должен быть внутри [разрешённого каталога](https://www.home-assistant.io/integrations/homeassistant/#allowlist_external_dirs) (например, `/media`). |
| `duration` | Нет | Известная длительность клипа в секундах, чтобы удерживать звонок на время проигрывания. Если не указана, проигрывание отслеживается до завершения звонка или до предела в 60 с. |
| `ring_duration` | Нет | Сколько секунд звонить до отказа (1–120, по умолчанию `30`). Клип проигрывается только если на звонок ответили в этом окне. |
| `volume` | Нет | Громкость проигрывания, `0`–`100` (по умолчанию `90`). |

Сервис **возвращает ответ** `{"answered": <bool>, "played": <bool>}` — `played` равно `true` только если на звонок ответили и клип был в него проигран.

> **Аудио должно быть AMR-NB (8 кГц, моно).** Это формат, который SIM800C проигрывает нативно. См. [Подготовка файла AMR-NB](#подготовка-файла-amr-nb) ниже. Флеш-память модема мала (~90 КБ), поэтому держите клипы примерно до минуты.

Пример автоматизации — голосовое оповещение звонком с откатом на SMS, если не ответили:

```yaml
automation:
  - alias: "Voice-call alert on a water leak"
    triggers:
      - trigger: state
        entity_id: binary_sensor.water_leak
        to: "on"
    actions:
      - action: sim800c.call_and_play
        data:
          target: "+79990001122"
          audio_file: "/media/sim800c/alert.amr"
          duration: 5
        response_variable: result
      - if: "{{ not result.answered }}"
        then:
          - action: sim800c.send_sms
            data:
              target: "+79990001122"
              message: "⚠️ Water leak detected at home! (call went unanswered)"
```

#### Подготовка файла AMR-NB

`call_and_play` нужен файл **AMR-NB (8 кГц, моно)**. Сгенерируйте речь/аудио любым инструментом (TTS-движок, запись и т.п.), затем закодируйте в AMR-NB.

> **Важно:** многие сборки `ffmpeg` — включая стандартную сборку **Homebrew** на macOS и `ffmpeg`, встроенный в Home Assistant OS — собраны **без** AMR-энкодера, поэтому `-c:a libopencore_amrnb` падает с ошибкой `Unknown encoder 'libopencore_amrnb'`. Нужен либо ffmpeg, собранный с `--enable-libopencore-amrnb`, либо крошечный отдельный энкодер ниже.

**Вариант A — ffmpeg с AMR-энкодером** (проверьте свой: `ffmpeg -encoders | grep amr`):

```bash
ffmpeg -i input.wav -ar 8000 -ac 1 -c:a libopencore_amrnb -b:a 12.2k alert.amr
```

Если в вашем `ffmpeg` нет энкодера, соберите его из исходников (в `build/ffmpeg-amr/`, системный ffmpeg не трогается) прилагаемым скриптом — он ставит `opencore-amr` и компилирует GPL-сборку ffmpeg с `--enable-libopencore-amrnb` (macOS/Homebrew и Debian/Ubuntu):

```bash
scripts/build-ffmpeg-amr.sh
# затем: build/ffmpeg-amr/bin/ffmpeg -i input.wav -ar 8000 -ac 1 -c:a libopencore_amrnb -b:a 12.2k alert.amr
```

**Вариант B — энкодер на ~20 строк на библиотеке opencore-amr** (работает, когда в ffmpeg нет энкодера, например на macOS/Homebrew):

```bash
# 1. Установите библиотеку (macOS: Homebrew; Debian/Ubuntu: apt install libopencore-amrnb-dev)
brew install opencore-amr

# 2. Соберите небольшой энкодер PCM->AMR-NB
cat > pcm2amr.c <<'EOF'
#include <stdio.h>
#include <string.h>
#include <opencore-amrnb/interf_enc.h>
#define MODE MR122   /* 12.2 kbps */
#define FRAME 160    /* 20 ms @ 8 kHz */
int main(void) {
    void *enc = Encoder_Interface_init(0);
    if (!enc) return 1;
    fwrite("#!AMR\n", 1, 6, stdout);           /* AMR file magic */
    short pcm[FRAME]; unsigned char out[64]; size_t n;
    while ((n = fread(pcm, sizeof(short), FRAME, stdin)) > 0) {
        if (n < FRAME) memset(pcm + n, 0, (FRAME - n) * sizeof(short));
        int b = Encoder_Interface_Encode(enc, MODE, pcm, out, 0);
        if (b > 0) fwrite(out, 1, b, stdout);
    }
    Encoder_Interface_exit(enc);
    return 0;
}
EOF
P=$(brew --prefix opencore-amr)   # на Linux уберите флаги -I/-L
clang pcm2amr.c -I$P/include -L$P/lib -lopencore-amrnb -o pcm2amr

# 3. Конвертация: любое аудио -> 8 кГц моно PCM -> AMR-NB (ffmpeg здесь только декодирует)
ffmpeg -y -i input.wav -ar 8000 -ac 1 -f s16le - | ./pcm2amr > alert.amr
```

Затем скопируйте `alert.amr` в разрешённый каталог, например `/media/sim800c/` (через Media-браузер, аддон Samba или `scp`), и укажите его в `audio_file`.

### Сброс звонка

```yaml
service: sim800c.hang_up
```

### Ответ на звонок с записью (и распознаванием)

`sim800c.answer_and_record` отвечает на **входящий звонок**, записывает то, что говорит собеседник, во флеш модема, сбрасывает звонок, затем распознаёт запись через локальный **Whisper-совместимый** STT-сервис (например, [GigaAM]) и возвращает результат:

```yaml
action: sim800c.answer_and_record
data:
  record_seconds: 15        # необязательно, 1-60 (по умолчанию 15)
  stt_url: "http://192.168.1.10:9000/v1"   # необязательное переопределение на вызов
response_variable: rec
```

Ответ — `{"recorded": bool, "transcript": str | null, "path": str | null}`.
Запись сохраняется в `<config>/media/sim800c/rec_<epoch>.amr`. Последний
транскрипт также доступен через `sensor.sim800c_last_recording` (с атрибутами
`caller`, `path`, `url`, `transcript` и `timestamp`), и срабатывает
**событие** `sim800c_call_recorded` с теми же полями.

Если STT-сервис недоступен, запись всё равно сохраняется и возвращается —
только `transcript` будет `null` (и в лог пишется предупреждение).

> **STT URL на Home Assistant OS:** значение по умолчанию `http://127.0.0.1:9000/v1`
> указывает на сам контейнер HA, а не на ваш STT-хост. На HAOS укажите
> **LAN-IP** STT-сервиса (например, `http://192.168.1.10:9000/v1`) в поле `stt_url`.

[GigaAM]: https://github.com/salute-developers/GigaAM

### Определение входящих звонков

Когда кто-то звонит на SIM, происходит два события:

- `binary_sensor.sim800c_incoming_call` переходит в **on**, пока телефон звонит. Его атрибут `caller` содержит номер звонящего (требуется определение номера / `+CLIP`, который интеграция включает автоматически).
- Срабатывает **событие** `sim800c_incoming_call` с `{"caller": "+7..."}`.

Атрибут `caller` бинарного сенсора очищается по завершении звонка. Если нужно, чтобы номер последнего звонящего сохранялся после звонка (например, для уведомления о пропущенном), читайте `sensor.sim800c_last_caller` — он хранит номер последнего входящего звонящего, пока его не заменит следующий звонок.

Пример автоматизации на входящий звонок:

```yaml
automation:
  - alias: "Announce incoming call"
    triggers:
      - trigger: event
        event_type: sim800c_incoming_call
    actions:
      - action: notify.mobile_app
        data:
          message: "Incoming call from {{ trigger.event.data.caller }}"
```

Или по состоянию бинарного сенсора:

```yaml
    triggers:
      - trigger: state
        entity_id: binary_sensor.sim800c_incoming_call
        to: "on"
```

> **Примечание:** интеграция не отвечает на входящие звонки (нет аудио-канала); она только сообщает о них. Входящие звонки определяются опросом модема каждые несколько секунд, поэтому очень короткий звонок иногда может быть пропущен.

## Примеры автоматизаций

Все номера ниже — заглушки, замените их своими.

### Дозвон-оповещение по событию (уведомление о пропущенном)

Позвонить вам на телефон (без звука, просто заставить его звонить), когда происходит что-то важное, например срабатывает сигнализация:

```yaml
automation:
  - alias: "Ring me when the alarm triggers"
    triggers:
      - trigger: state
        entity_id: alarm_control_panel.home
        to: "triggered"
    actions:
      - action: sim800c.call
        data:
          target: "+79990001122"
          ring_duration: 20
```

### Звонок с откатом на SMS, если не ответили

Используйте ответ сервиса для ветвления: если никто не берёт трубку, отправить SMS.

```yaml
automation:
  - alias: "Water leak: call, else SMS"
    triggers:
      - trigger: state
        entity_id: binary_sensor.water_leak
        to: "on"
    actions:
      - action: sim800c.call
        data:
          target: "+79990001122"
          ring_duration: 25
        response_variable: call_result
      - if:
          - condition: template
            value_template: "{{ not call_result.answered }}"
        then:
          - action: sim800c.send_sms
            data:
              target: "+79990001122"
              message: "⚠️ Water leak detected at home! (call went unanswered)"
```

### Повторять звонок, пока не ответят

Сделать несколько попыток, останавливаясь, как только трубку возьмут.

```yaml
automation:
  - alias: "Insist until answered"
    triggers:
      - trigger: state
        entity_id: binary_sensor.freezer_door
        to: "on"
        for: "00:10:00"
    actions:
      - repeat:
          count: 3
          sequence:
            - action: sim800c.call
              data:
                target: "+79990001122"
                ring_duration: 25
              response_variable: call_result
            - if:
                - condition: template
                  value_template: "{{ call_result.answered }}"
              then:
                - stop: "Answered"
            - delay: "00:01:00"
```

### Уведомление о входящем звонке (с номером)

```yaml
automation:
  - alias: "Notify on incoming call"
    triggers:
      - trigger: event
        event_type: sim800c_incoming_call
    actions:
      - action: notify.mobile_app_phone
        data:
          title: "📞 Incoming call"
          message: "From {{ trigger.event.data.caller or 'unknown number' }}"
```

### «Звонок как триггер» — действовать только по конкретному номеру

Превратить входящий звонок с известного номера в действие (например, открыть ворота). Интеграция никогда не отвечает, так что с звонящего не списываются деньги — это бесплатный триггер. Ограничьте доверенными номерами.

```yaml
automation:
  - alias: "Open gate on call from a trusted number"
    triggers:
      - trigger: event
        event_type: sim800c_incoming_call
    conditions:
      - condition: template
        value_template: >-
          {{ trigger.event.data.caller in
             ['+79990001122', '+79990003344'] }}
    actions:
      - action: switch.turn_on
        target:
          entity_id: switch.gate_relay
```

### Логирование пропущенных звонков

```yaml
automation:
  - alias: "Log missed calls"
    triggers:
      - trigger: state
        entity_id: binary_sensor.sim800c_incoming_call
        to: "off"
    conditions:
      - condition: template
        value_template: "{{ trigger.from_state.attributes.caller is not none }}"
    actions:
      - action: logbook.log
        data:
          name: "SIM800C"
          message: "Missed call from {{ trigger.from_state.attributes.caller }}"
```

> **Подсказка:** идентификаторы сущностей выше (`binary_sensor.sim800c_incoming_call` и т.п.) могут иметь префикс зоны модема — например, `binary_sensor.hallway_sim800c_incoming_call` — если вы назначили устройству зону. Точные ID смотрите в **Настройки → Устройства и службы → SIM800C**.

## Диагностические сенсоры

Интеграция создаёт следующие сенсоры для каждого настроенного модема:

- `sensor.sim800c_signal` — уровень сигнала в дБм.
- `sensor.sim800c_network` — состояние регистрации в сети (`registered` или `searching`).
- `sensor.sim800c_call_state` — текущее состояние звонка (`idle` / `dialing` / `ringing` / `active` / `incoming`), обновляется вживую.
- `sensor.sim800c_last_sms` — текст последнего принятого SMS, с атрибутами `sender`, `text` и `timestamp`.
- `sensor.sim800c_last_sms_sender` — номер последнего отправителя SMS (`sender` как состояние сенсора, по аналогии с `sensor.sim800c_last_caller`), сохраняется до следующего сообщения.
- `sensor.sim800c_last_caller` — номер последнего входящего звонящего. В отличие от атрибута `caller` бинарного сенсора (который очищается по завершении звонка), это значение сохраняется после окончания звонка, так что номер пропущенного остаётся доступен.
- `sensor.sim800c_last_recording` — транскрипт последнего записанного звонка (через `sim800c.answer_and_record`), с атрибутами `caller`, `path`, `url`, `transcript` и `timestamp`.
- `binary_sensor.sim800c_incoming_call` — `on`, пока идёт входящий звонок, с номером звонящего в атрибуте `caller`.

Сенсоры сигнала и сети опрашиваются периодически; сенсоры состояния звонка, входящего звонка и последнего SMS обновляются по мере поступления звонков и сообщений. Все они пригодны для автоматизаций и дашбордов, чтобы следить за состоянием модема и активностью.

## Устранение неполадок

### Включить отладочный лог

Добавьте в `configuration.yaml`:

```yaml
logger:
  logs:
    custom_components.sim800c: debug
```

### Проблемы с правами на последовательное устройство

Если при доступе к `/dev/ttyUSB0` возникают ошибки `Permission denied`, используйте прилагаемый скрипт:

**Быстрое решение:**

Запустите скрипт `FIX_USB_ON_HOST.sh` **на хост-машине** (не в контейнере):

```bash
bash /path/to/ha-sim800c/FIX_USB_ON_HOST.sh
```

Этот скрипт:
- ✅ Проверит наличие устройства
- ✅ Выдаст временные права (chmod 666)
- ✅ Создаст постоянное правило udev для автоматических прав
- ✅ Покажет команды перезапуска Home Assistant

**Ручное решение:**

Либо задайте права вручную:

```bash
# На хост-машине
sudo chmod 666 /dev/ttyUSB0
```

### Проблемы с правами (альтернативные методы)

**Для Home Assistant Core (только ручная установка):**

Если возникают ошибки прав при доступе к последовательному устройству, добавьте пользователя Home Assistant в группу `dialout`:

```bash
sudo usermod -a -G dialout homeassistant
```

Затем перезапустите Home Assistant.

**Для Home Assistant Container (Docker):**

Пробросьте устройство в контейнер и выдайте нужные права:

```bash
docker run ... --device=/dev/ttyUSB0:/dev/ttyUSB0 --group-add dialout ...
```

Либо используйте флаг `--privileged` (менее безопасно, но проще).

**Для Home Assistant OS:** последовательные устройства должны работать автоматически. Если нет, проверьте видимость устройства в Настройки → Система → Оборудование.

### Модуль не отвечает

1. Проверьте, что SIM-карта вставлена и есть сигнал сети.
2. Убедитесь, что путь к устройству верный.
3. Попробуйте другую скорость порта (частые значения: 9600, 115200).
4. Проверьте питание модуля SIM800C (некоторым нужен внешний источник питания).

## Требования к оборудованию

- GSM-модуль SIM800C
- USB-to-Serial адаптер (если нет встроенного USB)
- Активная SIM-карта с поддержкой SMS
- Питание для модуля (некоторым нужно внешнее питание 5В/2А)

## Проверено на

- Модулях SIM800C с USB-интерфейсом
- Home Assistant OS
- Home Assistant Container
- Home Assistant Core

## Разработка

Основано на шаблоне [integration_blueprint](https://github.com/ludeeus/integration_blueprint).

### Среда разработки

В проекте есть конфигурация devcontainer для удобной разработки в VSCode:

1. Откройте проект в VSCode с расширением Dev Containers
2. Контейнер автоматически смонтирует `/dev/ttyUSB0`
3. Если возникают ошибки прав, запустите `FIX_USB_ON_HOST.sh` на хост-машине
4. Запустите Home Assistant командой: `bash scripts/develop`
5. Откройте http://localhost:8123

### Тестирование на реальном оборудовании

Используйте `scripts/modem_harness.py`, чтобы общаться с реальным модулем SIM800C вне Home Assistant:

```bash
python3 scripts/modem_harness.py --device /dev/ttyUSB0 status
python3 scripts/modem_harness.py --device /dev/ttyUSB0 send +79990001122 "Тест"
```

`status` показывает регистрацию в сети и уровень сигнала; `send` отправляет SMS и печатает ссылку `+CMGS`.

## Лицензия

MIT License

## Участие в разработке

Вклад приветствуется! Присылайте Pull Request.
