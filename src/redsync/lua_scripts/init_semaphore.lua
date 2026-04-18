local list_key = KEYS[1]
local meta_key = KEYS[2]
local n = tonumber(ARGV[1])
local token = ARGV[2]

local existing_count = redis.call('HGET', meta_key, 'count')

if existing_count then
    return tonumber(existing_count)
end

local current_len = redis.call('LLEN', list_key)

if current_len == 0 then
    local tokens = {}
    for i = 1, n do
        tokens[i] = token
    end
    redis.call('RPUSH', list_key, unpack(tokens))
    redis.call('HSET', meta_key, 'count', n)
    return n
end

return current_len
