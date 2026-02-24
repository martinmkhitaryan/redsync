local key = KEYS[1]
local n = tonumber(ARGV[1])
local token = ARGV[2]
local current_len = redis.call('LLEN', key)

if current_len == 0 then
    local tokens = {}
    for i = 1, n do
        tokens[i] = token
    end
    redis.call('RPUSH', key, unpack(tokens))
    return n
end

return current_len
